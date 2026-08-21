"""Theme — lets any widget name its colours instead of hardcoding them.

A widget option that takes a colour may be given a **palette name** instead::

    v_label = Label(f_cc, text="Part", bg="page", fg="muted")

:func:`install` wraps ``tkinter.BaseWidget.__init__`` — the single seam every
classic Tk widget passes through — and, before Tk builds the widget, swaps any
such name for the colour the active palette gives it.  The widget is created
once, with real colours, exactly as if they had been written literally.

What each option was *named* is kept on the widget as ``_vcolors``::

    entry._vcolors.bg          # -> "field"
    entry._vcolors.as_dict()   # -> {"bg": "field", "fg": "text"}

which is the whole mechanism for switching palettes: :func:`apply` walks the
widgets that carry a ``_vcolors`` and re-resolves each name.  No comparing
against old values, no guessing what belongs to whom, and nothing to do per
frame — a widget that never named a palette colour is never touched, and a
literal ``bg="#ffffff"`` is left exactly as written, forever.

``ttk`` widgets take no ``bg``/``fg`` at all; they arrive here as
``"ttk::frame"`` and are skipped, and are styled through :class:`ttk.Style`
instead (see :func:`restyle_ttk`).
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from weakref import WeakKeyDictionary

__all__ = ["install", "uninstall", "installed", "apply", "current", "ensure",
           "exclude", "restyle_ttk", "VColors", "COLOR_OPTIONS",
           "name_to_color", "track"]

#: Widget options whose value is a colour.  A string given to one of these is
#: looked up in the palette; anything not in this set is passed through
#: untouched, so ``text="page"`` stays the word "page".
COLOR_OPTIONS = frozenset({
    "background", "bg",
    "foreground", "fg",
    "activebackground", "activeforeground",
    "disabledforeground", "disabledbackground",
    "highlightbackground", "highlightcolor",
    "selectbackground", "selectforeground", "selectcolor",
    "insertbackground", "troughcolor", "buttonbackground",
    "readonlybackground", "inactiveselectbackground",
    "activefill", "active_fill", "fill", "outline", "corner_bg",
})


class VColors:
    """The palette names a widget's colour options were given.

    Attribute access mirrors the spelling the caller used --- a widget built
    with ``bg="page"`` has ``_vcolors.bg == "page"``; one built with
    ``background="page"`` has ``_vcolors.background``.  Unset options raise
    ``AttributeError``, so ``getattr(w._vcolors, "fg", None)`` is the safe
    probe.
    """

    __slots__ = ("_names",)

    def __init__(self, names: dict):
        object.__setattr__(self, "_names", dict(names))

    def __getattr__(self, option):
        try:
            return object.__getattribute__(self, "_names")[option]
        except KeyError:
            raise AttributeError(option) from None

    def __contains__(self, option) -> bool:
        return option in self._names

    def as_dict(self) -> dict:
        """``{option: palette name}`` for every option that named a colour."""
        return dict(self._names)

    def items(self):
        return self._names.items()

    def __repr__(self) -> str:
        return f"VColors({self._names!r})"


_orig_init = None                    # the unpatched BaseWidget.__init__
_current = None                      # the Palette names resolve against
_tracked: WeakKeyDictionary = WeakKeyDictionary()   # widget -> VColors
_excluded: WeakKeyDictionary = WeakKeyDictionary()  # widget -> True
#: widget -> ({attribute: name}, apply_fn) for colours a widget holds itself
#: rather than as Tk options (see :func:`track`).
_custom: WeakKeyDictionary = WeakKeyDictionary()


# ── Install / uninstall ────────────────────────────────────────────────────

def install() -> None:
    """Begin resolving palette names in widget options.  Idempotent.

    Wraps ``tkinter.BaseWidget.__init__``.  Widgets built before this runs
    never saw a palette name (it would have been a Tk colour error), so there
    is nothing to retrofit.
    """
    global _orig_init
    if _orig_init is not None:
        return
    _orig_init = tk.BaseWidget.__init__

    def __init__(self, master, widgetName, cnf={}, kw={}, extra=()):
        named = None
        # ``widgetName`` can be None for base ``tk.Widget(master, None)``
        # construction (e.g. tkinterweb's Tkhtml binding); such widgets take
        # no palette options, so skip resolution rather than crash on None.
        if _current is not None and widgetName is not None and not widgetName.startswith("ttk::"):
            cnf, kw, named = _resolve(cnf, kw)
        _orig_init(self, master, widgetName, cnf, kw, extra)
        if named:
            vcolors = VColors(named)
            object.__setattr__(self, "_vcolors", vcolors)
            _tracked[self] = vcolors

    tk.BaseWidget.__init__ = __init__


def uninstall() -> None:
    """Restore Tk's own widget construction and forget every tracked widget."""
    global _orig_init
    if _orig_init is None:
        return
    tk.BaseWidget.__init__ = _orig_init
    _orig_init = None
    _tracked.clear()


def installed() -> bool:
    """True while widget construction is being intercepted."""
    return _orig_init is not None


def ensure() -> None:
    """Guarantee that names resolve, arming with the app default if needed.

    VIStk's own widgets name palette colours, so they must not depend on
    something else having applied a palette first — a ``TabManager`` built
    before the Host resolves settings, or a screen run standalone, would
    otherwise hand Tk the literal name and fail.  Cheap and idempotent.
    """
    if _current is None:
        from VIStk.Styles._palette import default_palette, resolve_palette
        apply(resolve_palette(default_palette()))


def current():
    """The :class:`~VIStk.Styles.Palette` names currently resolve against."""
    return _current


def exclude(widget) -> None:
    """Stop repainting *widget* when the palette changes."""
    _excluded[widget] = True
    _tracked.pop(widget, None)


# ── Resolution ─────────────────────────────────────────────────────────────

def _swap(source, named: dict):
    """Return *source* with palette names replaced by colours.

    Where a colour is expected, a value that *is* a colour is passed through —
    a ``#rrggbb`` literal, or anything that isn't a plain string (a ``wColor``,
    say).  Any other string is a name, so it goes through the palette; if the
    palette doesn't define it, it is left for Tk, which accepts its own colour
    names (``"red"``) and rejects the rest with a normal error.

    Options outside :data:`COLOR_OPTIONS` are never looked at, so ``text="page"``
    stays the word "page".  A copy is made only when something actually
    changes, so the common case allocates nothing.
    """
    if not isinstance(source, dict) or not source:
        return source
    swapped = None
    for option, value in source.items():
        if (option in COLOR_OPTIONS and type(value) is str
                and not value.startswith("#")):
            colour = _current.get(value, None)
            if colour is not None:
                if swapped is None:
                    swapped = dict(source)
                swapped[option] = colour
                named[option] = value
    return source if swapped is None else swapped


def _resolve(cnf, kw):
    """Swap palette names in both option dicts; report what was named."""
    named: dict = {}
    return _swap(cnf, named), _swap(kw, named), named


def name_to_color(value):
    """``(colour, name)`` for a value given where a colour is expected.

    The same rule the interception applies, exposed for widget classes that
    take colour arguments of their own — a ``vButton``'s ``outline`` or
    ``active_fill``, say.  Those are consumed by the widget before Tk ever
    sees them, so they never reach the constructor seam and have to be
    resolved here instead.

    Returns the value unchanged with a ``None`` name when it is already a
    colour (or the palette doesn't define it), so a caller can store the
    colour and use the name to re-resolve on a palette switch.
    """
    if (_current is not None and type(value) is str
            and not value.startswith("#")):
        colour = _current.get(value, None)
        if colour is not None:
            return colour, value
    return value, None


def track(widget, names: dict, apply_fn) -> None:
    """Follow *widget* on palette switches through a widget-specific setter.

    *names* is ``{attribute: palette name}`` and *apply_fn* is called with
    ``{attribute: colour}`` each time the palette changes — for colours a
    widget holds itself rather than as Tk options.
    """
    if names:
        _custom[widget] = (dict(names), apply_fn)


def apply(palette) -> None:
    """Make *palette* current and re-resolve every widget that named a colour.

    Only widgets carrying a ``_vcolors`` are touched, and each option is set
    straight back to whatever its name now means — there is nothing to
    compare, because a widget that was given a literal colour never entered
    this bookkeeping in the first place.
    """
    global _current
    install()          # a palette being applied is the only cue resolution needs
    _current = palette
    for widget, vcolors in list(_tracked.items()):
        if widget in _excluded:
            continue
        try:
            widget.configure(**{option: palette.get(name)
                                for option, name in vcolors.items()
                                if palette.get(name) is not None})
        except tk.TclError:
            continue        # widget destroyed, or the option no longer applies
    for widget, (names, apply_fn) in list(_custom.items()):
        if widget in _excluded:
            continue
        try:
            apply_fn({attr: palette.get(name) for attr, name in names.items()
                      if palette.get(name) is not None})
        except tk.TclError:
            continue
    restyle_ttk(palette)


# ── ttk ────────────────────────────────────────────────────────────────────

def restyle_ttk(palette, theme: str | None = None) -> None:
    """Push *palette* into :class:`ttk.Style`, optionally switching theme first.

    ttk widgets can't take a colour per instance, so they follow the palette
    through their styles instead.  How much lands depends on the theme: the
    Windows ``vista``/``xpnative`` themes draw buttons, entries, comboboxes,
    notebook tabs and scrollbars with native elements that ignore colour
    options, while ``clam``/``alt``/``default`` draw everything in Tk.  The
    theme is the app's choice (``Project.setWidgetTheme``).

    Reads the conventional names (``surface``, ``text``, ``field`` …) and
    silently skips any a palette doesn't define.  Never raises — ttk styling
    must not stop a window opening.
    """
    def colour(name):
        return palette.get(name)

    try:
        style = ttk.Style()
        if theme and theme in style.theme_names():
            style.theme_use(theme)

        def configure(target, **names):
            options = {opt: colour(name) for opt, name in names.items()
                       if colour(name) is not None}
            if options:
                style.configure(target, **options)

        configure(".", background="surface", foreground="text",
                  fieldbackground="field", troughcolor="surface_alt",
                  bordercolor="border", darkcolor="surface_alt",
                  lightcolor="surface_alt")
        configure("TFrame", background="surface")
        configure("TLabel", background="surface", foreground="text")
        configure("TLabelframe", background="surface")
        configure("TLabelframe.Label", background="surface", foreground="text")
        configure("TButton", background="button", foreground="button_text")
        configure("TCheckbutton", background="surface", foreground="text")
        configure("TRadiobutton", background="surface", foreground="text")
        configure("TEntry", fieldbackground="field", foreground="field_text")
        configure("TCombobox", fieldbackground="field", foreground="field_text")
        configure("TNotebook", background="surface")
        configure("TNotebook.Tab", background="tab_inactive", foreground="tab_fg")
        configure("Treeview", background="field", fieldbackground="field",
                  foreground="field_text")
        configure("Treeview.Heading", background="button", foreground="button_text")
        configure("TSeparator", background="border")
        configure("TProgressbar", background="accent", troughcolor="surface_alt")
        configure("TScrollbar", background="button", troughcolor="surface_alt")
        configure("TPanedwindow", background="surface")

        if colour("button_hover") is not None:
            style.map("TButton", background=[("active", colour("button_hover"))])
        if colour("selection") is not None:
            style.map("Treeview",
                      background=[("selected", colour("selection"))],
                      foreground=[("selected", colour("selection_text"))])
        if colour("tab_active") is not None:
            style.map("TNotebook.Tab",
                      background=[("selected", colour("tab_active"))],
                      foreground=[("selected", colour("tab_active_fg"))])
    except tk.TclError:
        pass
