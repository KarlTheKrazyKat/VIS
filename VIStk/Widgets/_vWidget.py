"""vWidget (0.6.2) — shared base for the v-prefixed widget family.

``vWidget`` is the common base behind :class:`~VIStk.Widgets.vLabel`,
:class:`~VIStk.Widgets.vButton` and :class:`~VIStk.Widgets.vFrame`, in the
same spirit as tkinter's own :class:`tkinter.Widget` base.  It is a pure
mixin (subclasses ``object``, never ``tk.Widget``) and is combined with a
native classic-tk widget via multiple inheritance::

    class vLabel(vWidget, Label):   ...
    class vButton(vWidget, Button): ...
    class vFrame(vWidget, LayoutFrame): ...

so a ``vLabel`` genuinely *is* both a ``vWidget`` and a ``tk.Label`` (both
``isinstance`` checks pass).  ``vWidget.__init__`` runs first in the MRO,
computes inheritance and pops the rounded-corner kwargs, then defers the
actual Tcl-widget creation to the native base through cooperative
``super().__init__()`` — so the underlying widget is created exactly once.

It adds two capabilities on top of the native widget:

1. **Parent-property inheritance.**  Each subclass declares an ``_INHERIT``
   tuple of option names (``"background"``, ``"foreground"``, ``"font"``);
   any of those the caller did *not* pass explicitly are filled in from the
   parent widget at construction time.  Explicitly-passed options always
   win.  Inheritance is a one-time snapshot; call :meth:`refresh` to re-pull.

2. **Optional rounded corners.**  Opt-in via ``radius`` (default ``0`` → a
   plain native widget, no extra machinery).  When ``radius > 0`` the corner
   fill is painted with an anti-aliased PIL rounded-rectangle image that is
   regenerated whenever the widget is resized.  The classic tk widgets are
   always rectangular, so the rounded look is achieved by compositing this
   image (subclasses decide *where* it is painted via :meth:`_paint`).

Rounded kwargs (popped before the native ``__init__`` so tk never sees them):

``radius``         corner radius in px (``0`` disables rounded rendering).
``outline``        optional stroke colour drawn around the rounded rect.
``outline_width``  stroke width in px (default ``1``; only used with outline).
``corner_bg``      colour painted into the corners so they blend; defaults to
                   the parent's background (a solid-colour parent is assumed,
                   same as the existing Canvas-based pills).
"""

from __future__ import annotations

from tkinter import *
from tkinter import ttk
import tkinter as _tk
from PIL import Image, ImageDraw
from PIL.Image import Resampling
import PIL.ImageTk


def rounded_pil_image(width: int, height: int, radius: int,
                      fill: tuple[int, int, int],
                      corner_bg: tuple[int, int, int],
                      outline: tuple[int, int, int] | None = None,
                      outline_width: int = 0,
                      supersample: int = 4) -> "Image.Image":
    """Render an anti-aliased rounded-rectangle as a **PIL ``Image``**.

    Same shape as :func:`make_rounded_image`, but returns the raw RGB image so
    callers can crop it (e.g. ``vFrame`` floats exact corner crops on top of its
    children to round them) before handing it to Tk.  The rectangle is filled
    with *fill*; the area outside the rounded corners is *corner_bg* so it blends
    on a solid-colour parent.  Colours are RGB 0-255 tuples (resolve Tk names
    with :meth:`vWidget._resolve_color` first).  Drawn at *supersample*×
    resolution and Lanczos-downscaled for smooth edges.

    Args:
        width:          Target width in px.
        height:         Target height in px.
        radius:         Corner radius in px (clamped to half the short side).
        fill:           Interior colour, ``(r, g, b)``.
        corner_bg:      Corner / blend colour, ``(r, g, b)``.
        outline:        Optional stroke colour, ``(r, g, b)`` or ``None``.
        outline_width:  Stroke width in px (ignored without *outline*).
        supersample:    Oversampling factor for anti-aliasing (default 4).
    """
    width = max(1, int(width))
    height = max(1, int(height))
    ss = max(1, int(supersample))
    big_w, big_h = width * ss, height * ss
    r = max(0, int(radius)) * ss
    r = min(r, big_w // 2, big_h // 2)

    img = Image.new("RGB", (big_w, big_h), corner_bg)
    draw = ImageDraw.Draw(img)
    has_outline = outline is not None and outline_width > 0
    draw.rounded_rectangle(
        (0, 0, big_w - 1, big_h - 1),
        radius=r,
        fill=fill,
        outline=outline if has_outline else None,
        width=(outline_width * ss) if has_outline else 1,
    )
    return img.resize((width, height), resample=Resampling.LANCZOS)


def make_rounded_image(width: int, height: int, radius: int,
                       fill: tuple[int, int, int],
                       corner_bg: tuple[int, int, int],
                       outline: tuple[int, int, int] | None = None,
                       outline_width: int = 0,
                       supersample: int = 4) -> "PIL.ImageTk.PhotoImage":
    """Render an anti-aliased rounded-rectangle as a ``PhotoImage``.

    Thin wrapper over :func:`rounded_pil_image` that wraps the result in a
    ``PIL.ImageTk.PhotoImage``.  The caller must keep a reference to the returned
    image or Tk will garbage-collect it.  See :func:`rounded_pil_image` for the
    arguments.
    """
    return PIL.ImageTk.PhotoImage(
        rounded_pil_image(width, height, radius, fill, corner_bg,
                          outline=outline, outline_width=outline_width,
                          supersample=supersample))


# ── Native-option doc surfacing ────────────────────────────────────────────────
# tkinter hides each widget's options behind **kw and only lists them in the
# widget's __init__ docstring (Label/Button: "STANDARD OPTIONS"; Frame: "Valid
# resource names").  We lift that block straight from tkinter at class-creation
# time and append it to each v-widget's __init__ doc, so help()/REPL/Sphinx show
# the authoritative native options next to the v-widget's own params — always in
# sync with the installed Tk.  (Editor autocomplete is handled separately by the
# Unpack[TypedDict] hints in _vtypes.py.)
_OPT_MARKERS = ("STANDARD OPTIONS", "Valid resource names")


def _native_option_base(cls):
    """First tkinter-defined widget base of *cls* whose __init__ doc lists options."""
    for base in cls.__mro__:
        if base.__module__ == "tkinter" and issubclass(base, _tk.BaseWidget):
            doc = base.__init__.__doc__ or ""
            if any(m in doc for m in _OPT_MARKERS):
                return base
    return None


def _native_options_block(base) -> str:
    """The option section of *base*'s __init__ docstring, with a header."""
    doc = base.__init__.__doc__ or ""
    hits = [doc.find(m) for m in _OPT_MARKERS if m in doc]
    body = doc[min(hits):].rstrip() if hits else ""
    return (f"Native tkinter.{base.__name__} options "
            f"(accepted as keyword arguments / **kwargs)\n\n{body}")


# ── Resize → repaint, via a dedicated bindtag ──────────────────────────────────
# A rounded v-widget repaints on <Configure>.  Binding that on the widget
# instance is fragile: a caller's ``widget.bind("<Configure>", fn)`` without
# ``add="+"`` (e.g. wiring up fUtil.autosize) would silently replace it and the
# rounded image would stop updating (the widget renders square).  So the repaint
# lives on a shared, dedicated bindtag the caller's instance bind can't touch;
# one class-level dispatcher routes the event to the widget's own _render_rounded.
_RENDER_TAG = "vWidgetRounded"


def _render_dispatch(event):
    fn = getattr(event.widget, "_render_rounded", None)
    if fn is not None:
        fn(event)


class vWidget:
    """Shared base/mixin for the v-prefixed widgets (combine with a tk class).

    Subclasses set :attr:`_INHERIT` to the option names that should be pulled
    from the parent when omitted, and may override :meth:`_prepare_rounded` /
    :meth:`_paint` to control where the rounded image is composited.

    On subclass creation the native tk widget's option list is appended to the
    subclass's ``__init__`` docstring (see :func:`_native_options_block`), so
    ``help(vLabel)`` documents every accepted option, not just the v-widget
    additions.
    """

    #: Option names inherited from the parent when not passed explicitly.
    _INHERIT: tuple[str, ...] = ()

    #: Option names that, when reconfigured at runtime, force a rounded repaint.
    #: Subclasses extend this (e.g. vButton adds ``"state"``).
    _REPAINT_OPTS: tuple[str, ...] = ("background", "bg")

    def __init_subclass__(cls, **kw):
        super().__init_subclass__(**kw)
        init = cls.__dict__.get("__init__")
        if init is None or init.__doc__ is None:
            return
        try:
            base = _native_option_base(cls)
            if base is not None:
                init.__doc__ = (init.__doc__.rstrip() + "\n\n"
                                + _native_options_block(base))
        except Exception:
            pass

    def __init__(self, master=None, *,
                 radius: int = 0, outline: str | None = None,
                 outline_width: int = 1, corner_bg: str | None = None,
                 **kwargs):
        """Build the native widget with inheritance + optional rounded corners.

        ``master`` and any native widget options pass straight through to the
        underlying tk widget; only the rounded kwargs above are intercepted.
        """
        # Stash rounded config (set before super().__init__ — safe, these are
        # plain Python attributes on the object, not Tcl options).
        self._v_master = master
        self._v_radius = int(radius or 0)
        self._v_outline = outline
        self._v_outline_width = int(outline_width or 0)
        self._v_corner_bg = corner_bg
        self._v_bg_image = None              # keep a ref so Tk won't GC it
        self._v_last_size = (0, 0)           # debounce identical-size redraws

        # Record which options the caller set explicitly (canonical names) so
        # inheritance / refresh() never clobber them.
        self._v_explicit = self._canon_keys(kwargs)

        # Inheritance fills in only the omitted props; caller's kwargs win.
        merged = self._apply_inheritance(master, kwargs)

        # Defer actual widget creation to the native base (cooperative MRO).
        super().__init__(master, **merged)

        if self._v_radius > 0:
            self._prepare_rounded()
            # Precompute the corner-blend colour string (parent bg by default).
            self._v_corner = self._v_corner_bg or self._parent_bg(master)
            self._install_render_binding()

    def _install_render_binding(self) -> None:
        """Repaint on resize via a dedicated bindtag (see :data:`_RENDER_TAG`),
        so a caller's ``self.bind("<Configure>", ...)`` can't clobber rendering."""
        # Install the shared dispatcher once per Tk interpreter.
        if not self.bind_class(_RENDER_TAG, "<Configure>"):
            self.bind_class(_RENDER_TAG, "<Configure>", _render_dispatch, add="+")
        # Give this widget the tag (after its own tags, so a user's instance
        # <Configure> binding still runs — it just can no longer replace ours).
        tags = self.bindtags()
        if _RENDER_TAG not in tags:
            self.bindtags(tags + (_RENDER_TAG,))

    # ── Inheritance ──────────────────────────────────────────────────────────

    @staticmethod
    def _canon_keys(kwargs: dict) -> set[str]:
        """Caller-supplied option names, normalised to their canonical form
        (so ``bg``/``background`` and ``fg``/``foreground`` are equivalent)."""
        keys = set(kwargs)
        if "bg" in keys:
            keys.add("background")
        if "fg" in keys:
            keys.add("foreground")
        return keys

    @staticmethod
    def _read_parent_option(master, option: str, style_option: str) -> str | None:
        """Read *option* from *master*, handling classic AND ttk parents.

        Tries a classic ``cget`` first; ttk widgets raise for direct options
        like ``-background``, so fall back to their style's ``lookup``.
        Returns ``None`` when the option is absent or empty.
        """
        if master is None:
            return None
        try:
            val = master.cget(option)
            if val not in ("", None):
                return str(val)
        except Exception:
            pass
        try:
            val = ttk.Style(master).lookup(master.winfo_class(), style_option)
            if val:
                return str(val)
        except Exception:
            pass
        return None

    def _parent_bg(self, master) -> str:
        """Parent background colour, falling back to ``"SystemButtonFace"``."""
        return self._read_parent_option(master, "background", "background") \
            or "SystemButtonFace"

    def _apply_inheritance(self, master, kwargs: dict) -> dict:
        """Return *kwargs* augmented with inherited props the caller omitted."""
        if master is None:
            return kwargs
        merged = dict(kwargs)
        explicit = self._v_explicit
        for prop in self._INHERIT:
            if prop in explicit:
                continue
            val = self._read_parent_option(master, prop, prop)
            if val:
                merged[prop] = val
        return merged

    def refresh(self) -> None:
        """Re-pull inherited props (those never set explicitly) and repaint.

        Use after the parent's appearance changes, since inheritance is a
        one-time snapshot taken at construction.
        """
        master = self._v_master
        if master is not None:
            for prop in self._INHERIT:
                if prop in self._v_explicit:
                    continue
                val = self._read_parent_option(master, prop, prop)
                if val:
                    try:
                        self.configure(**{prop: val})
                    except Exception:
                        pass
        if self._v_radius > 0:
            self._v_corner = self._v_corner_bg or self._parent_bg(master)
            self._v_last_size = (0, 0)   # force a redraw at current size
            self._render_rounded()

    # ── Rounded rendering ────────────────────────────────────────────────────

    def _resolve_color(self, color: str | None) -> tuple[int, int, int] | None:
        """Resolve any Tk colour name/hex to an ``(r, g, b)`` 0-255 tuple.

        Uses ``winfo_rgb`` so it understands every name Tk does — standard
        names, ``greyNN``, hex, and system colours like ``SystemButtonFace``.
        """
        if not color:
            return None
        try:
            r, g, b = self.winfo_rgb(color)   # 16-bit per channel
            return (r // 256, g // 256, b // 256)
        except Exception:
            return None

    def _fill_color(self) -> tuple[int, int, int] | None:
        """The widget's own effective background, as an RGB tuple."""
        try:
            return self._resolve_color(self.cget("background"))
        except Exception:
            return None

    def _render_rounded(self, event=None) -> None:
        """`<Configure>` handler: regenerate the rounded image on size change."""
        w = self.winfo_width()
        h = self.winfo_height()
        if w <= 1 or h <= 1:
            return
        if (w, h) == self._v_last_size:
            return
        self._v_last_size = (w, h)

        fill = self._fill_color() or (255, 255, 255)
        corner = self._resolve_color(self._v_corner) or (240, 240, 240)
        outline = self._resolve_color(self._v_outline)
        img = make_rounded_image(w, h, self._v_radius, fill, corner,
                                 outline=outline,
                                 outline_width=self._v_outline_width)
        self._paint(img)

    def _prepare_rounded(self) -> None:
        """Configure *self* to show a centred background image.

        Borders / highlight / internal padding are zeroed so the painted image
        exactly covers the widget — this also prevents an image⇄requested-size
        feedback loop under content-sizing geometry managers.

        A 1×1 transparent placeholder image is installed immediately so that
        ``width`` / ``height`` are interpreted in **pixels** from the start
        (Tk reads them as character cells until the widget has an image), letting
        callers size a rounded widget in pixels without a first-frame flash.

        Subclasses that paint elsewhere (e.g. vFrame) override this.
        """
        self._v_bg_image = PhotoImage(master=self, width=1, height=1)
        self.configure(bd=0, highlightthickness=0, padx=0, pady=0,
                       compound="center", image=self._v_bg_image)

    def _paint(self, image: "PIL.ImageTk.PhotoImage") -> None:
        """Composite *image* onto the widget.  Default: set it as our image."""
        self._v_bg_image = image
        self.configure(image=image)

    def configure(self, cnf=None, **kw):
        """Native ``configure`` that also repaints when a rounded widget's fill
        changes — so runtime recolouring (``widget.configure(bg=...)``) and, for
        subclasses, state changes are reflected in the rounded image."""
        result = super().configure(cnf, **kw)
        if getattr(self, "_v_radius", 0) > 0:
            keys = set(kw)
            if isinstance(cnf, dict):
                keys |= set(cnf)
            if keys.intersection(self._REPAINT_OPTS):
                self._v_last_size = (0, 0)   # force a redraw at the current size
                self._render_rounded()
        return result

    config = configure
