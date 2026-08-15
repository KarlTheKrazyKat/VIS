"""Palette — an open ``name -> colour`` mapping, and the registry of the
palettes a user can choose between.

A palette is **not** a fixed schema.  It is a set of colour names an app picks
for itself, and widgets refer to those names instead of to colours::

    Project.registerPalette("bmi Light", {
        "page":  wColors.Lowlight.Button,
        "card":  wColors.White,
        "text":  wColors.Black,
        "muted": wColors.Grey.Light,
    })

    v_label = Label(f_cc, text="Part", bg="page", fg="muted")

The chrome is not special: the tab bar reads ``bar_bg`` / ``tab_active`` /
``tab_hover`` and friends out of the same mapping, so a palette can restyle it
by naming those, and a widget can borrow them by name like any other colour.

**Fallback.** Every palette has a *base* (``"light"`` unless told otherwise),
and a name it doesn't define resolves through that base.  So a palette is as
short as the app wants: name the handful of colours you care about and the
rest keep working.  :data:`LIGHT` and :data:`DARK` ship as the two roots, and
:data:`LIGHT` reproduces the greys the tab bar used before the styles system
existed, plus the Windows/Tk widget defaults.
"""
from __future__ import annotations

__all__ = ["Palette", "LIGHT", "DARK", "base_palette", "dim", "lift",
           "bar_companions", "register_palette", "get_palette",
           "palette_names", "offer_palettes", "offered_palettes",
           "default_palette", "set_default_palette", "set_system_palettes",
           "system_palettes", "resolve_palette", "CHROME_NAMES"]

#: The names VIStk's own chrome looks up.  Nothing enforces them — they are
#: the vocabulary the tab bar happens to use, listed so an app knows what it
#: can restyle.  Anything else in a palette is the app's own business.
CHROME_NAMES = (
    "bar_bg", "tab_active", "tab_inactive", "tab_hover", "close_hover",
    "separator", "accent", "empty", "empty_hover", "focused", "unfocused",
    "active_unfocused", "tab_drag", "tab_fg", "tab_active_fg",
    "info_bg", "info_fg",
)


class Palette:
    """An open mapping of colour *names* to Tk colours.

    Values may be anything Tk accepts — ``"#1874cd"``, ``"grey62"``, or an
    object that stringifies to a colour (a ``pywomlib`` ``wColor``).  A name
    that isn't defined here resolves through :attr:`base`, so palettes stack.

    Args:
        colors: ``{name: colour}``.  A :class:`Palette` may be passed instead
                and its own (non-inherited) colours are copied.
        base:   The palette to fall through to, or ``None`` for a root.
    """

    __slots__ = ("_colors", "_base")

    def __init__(self, colors=None, base=None):
        if isinstance(colors, Palette):
            colors = colors._colors
        self._colors: dict = dict(colors or {})
        self._base: "Palette | None" = base

    # ── Lookup ─────────────────────────────────────────────────────────────

    def get(self, name, default=None):
        """The colour for *name*, falling through :attr:`base`; else *default*."""
        palette = self
        while palette is not None:
            if name in palette._colors:
                return palette._colors[name]
            palette = palette._base
        return default

    def __getitem__(self, name):
        value = self.get(name, _MISSING)
        if value is _MISSING:
            raise KeyError(name)
        return value

    def __contains__(self, name) -> bool:
        return self.get(name, _MISSING) is not _MISSING

    def __getattr__(self, name):
        """``palette.surface`` — the attribute spelling of :meth:`get`.

        Only reached for names Python didn't find as real attributes, so it
        can't shadow the methods above.
        """
        value = self.get(name, _MISSING)
        if value is _MISSING:
            raise AttributeError(name)
        return value

    def names(self) -> set:
        """Every name this palette resolves, its base's included."""
        found = set()
        palette = self
        while palette is not None:
            found |= set(palette._colors)
            palette = palette._base
        return found

    @property
    def base(self):
        """The palette this one falls through to, or ``None``."""
        return self._base

    # ── Derivation ─────────────────────────────────────────────────────────

    def derive(self, **colors) -> "Palette":
        """A new palette layered on this one, overriding only *colors*.

        A value of ``"$name"`` copies another colour of the result, so a
        palette stays internally consistent without repeating itself.  Naming
        ``bar_bg`` without the bar's own states (``focused`` / ``unfocused`` /
        ``empty`` / ``empty_hover``) shades those from it — see
        :func:`bar_companions`.
        """
        literal = {k: v for k, v in colors.items()
                   if not (isinstance(v, str) and v.startswith("$"))}
        child = Palette(literal, base=self)
        refs = {k: child.get(v[1:]) for k, v in colors.items()
                if isinstance(v, str) and v.startswith("$")}
        child._colors.update(refs)
        if "bar_bg" in colors:
            for role, value in bar_companions(child.get("bar_bg"),
                                              skip=set(colors)).items():
                child._colors[role] = value
        return child

    @classmethod
    def from_preset(cls, base="light", **colors) -> "Palette":
        """Derive from a registered palette by name.  ``Palette.from_preset(
        "light", page=…)`` is ``get_palette("light").derive(page=…)``."""
        parent = base if isinstance(base, Palette) else (get_palette(base) or LIGHT)
        return parent.derive(**colors)

    def __repr__(self) -> str:
        return f"Palette({len(self._colors)} colours, base={'yes' if self._base else 'none'})"


_MISSING = object()


#: The pre-styles chrome greys and the Windows/Tk widget defaults, exactly —
#: so ``classic`` on ``light`` renders as it did before the styles system, and
#: a widget that names these colours looks like an unstyled Tk widget.
LIGHT = Palette({
    # Tab bar
    "bar_bg": "grey62", "tab_active": "grey85", "tab_inactive": "grey62",
    "tab_hover": "grey72", "close_hover": "IndianRed", "separator": "grey50",
    "accent": "dodger blue", "empty": "grey55", "empty_hover": "grey68",
    "focused": "grey62", "unfocused": "grey52", "active_unfocused": "grey65",
    "tab_drag": "grey45", "tab_fg": "black", "tab_active_fg": "black",
    "info_bg": "grey55", "info_fg": "grey88",
    # General UI — the Windows/Tk defaults (SystemButtonFace, SystemWindow,
    # SystemWindowText, the shell selection blue).
    "surface": "#f0f0f0", "surface_alt": "#ffffff", "border": "#c8c8c8",
    "text": "#000000", "text_muted": "#6b6b6b", "text_inverse": "#ffffff",
    "disabled_text": "#6d6d6d", "accent_hover": "#1c86ee",
    "button": "#f0f0f0", "button_hover": "#e5f1fb", "button_text": "#000000",
    "field": "#ffffff", "field_text": "#000000", "field_border": "#7a7a7a",
    "selection": "#0078d7", "selection_text": "#ffffff",
})

#: A dark root.  Same names, inverted.
DARK = Palette({
    "bar_bg": "grey25", "tab_active": "grey38", "tab_inactive": "grey25",
    "tab_hover": "grey32", "close_hover": "IndianRed", "separator": "grey40",
    "accent": "#4aa3ff", "empty": "grey22", "empty_hover": "grey30",
    "focused": "grey25", "unfocused": "grey18", "active_unfocused": "grey30",
    "tab_drag": "grey15", "tab_fg": "grey90", "tab_active_fg": "white",
    "info_bg": "grey20", "info_fg": "grey70",
    "surface": "#2b2b2b", "surface_alt": "#333333", "border": "#454545",
    "text": "#e6e6e6", "text_muted": "#9a9a9a", "text_inverse": "#1a1a1a",
    "disabled_text": "#6a6a6a", "accent_hover": "#69b4ff",
    "button": "#3a3a3a", "button_hover": "#464646", "button_text": "#e6e6e6",
    "field": "#1f1f1f", "field_text": "#e6e6e6", "field_border": "#5a5a5a",
    "selection": "#2f6fb3", "selection_text": "#ffffff",
})


# ── Registry ───────────────────────────────────────────────────────────────
# Insertion-ordered so the Settings dropdown offers palettes in a stable order.

_PALETTES: dict[str, Palette] = {}
_ORDER: list[str] = []
_OFFERED: list[str] | None = None
_DEFAULT: str = "light"
_SYSTEM_PAIR: tuple[str, str] = ("light", "dark")


def register_palette(name: str, colors, base="light") -> None:
    """Register (or replace) the palette *name*.

    *colors* is a ``{name: colour}`` mapping — or an existing
    :class:`Palette`, used as-is.  A plain mapping is layered on *base* (the
    shipped ``"light"`` unless told otherwise), so names it leaves out keep
    resolving.  Re-registering a name keeps its slot in the offered order.
    """
    if isinstance(colors, Palette):
        palette = colors
    else:
        parent = get_palette(base) if base is not None else None
        # Through derive(), so a registered mapping gets the same treatment a
        # derived one does: "$name" references resolve, and naming ``bar_bg``
        # shades the bar's own empty/unfocused states from it.
        palette = parent.derive(**colors) if parent else Palette(colors)
    if name not in _PALETTES:
        _ORDER.append(name)
    _PALETTES[name] = palette


def get_palette(name) -> Palette | None:
    """The registered :class:`Palette` for *name*, or ``None``.  Lookup is
    case-insensitive, so a stored ``"bmi light"`` still finds ``"bmi Light"``."""
    if name is None:
        return None
    if name in _PALETTES:
        return _PALETTES[name]
    lowered = str(name).lower()
    for key, palette in _PALETTES.items():
        if key.lower() == lowered:
            return palette
    return None


def palette_names() -> list:
    """Every registered palette name, in registration order."""
    return list(_ORDER)


def offer_palettes(names, default: str | None = None) -> None:
    """Curate which palette names the Settings window offers the user."""
    global _OFFERED
    _OFFERED = list(names)
    if default is not None:
        set_default_palette(default)


def offered_palettes() -> list:
    """The palette names the Settings window should offer (curated or all)."""
    return list(_OFFERED) if _OFFERED is not None else palette_names()


def default_palette() -> str:
    """The palette name used when the user has not chosen one."""
    return _DEFAULT


def set_default_palette(name: str) -> None:
    """Set the app's default palette by *name*.

    Raises ``ValueError`` for an unregistered name — a typo here would
    otherwise surface as the app silently wearing the stock greys.
    """
    global _DEFAULT
    if name != "system" and get_palette(name) is None:
        raise ValueError(
            f"Unknown palette {name!r}; register it first (have: {palette_names()})")
    _DEFAULT = name


def set_system_palettes(light: str, dark: str) -> None:
    """Name the pair ``"system"`` resolves to when following the OS theme."""
    global _SYSTEM_PAIR
    for name in (light, dark):
        if get_palette(name) is None:
            raise ValueError(f"Unknown palette {name!r}; register it first")
    _SYSTEM_PAIR = (light, dark)


def system_palettes() -> tuple:
    """The ``(light, dark)`` names ``"system"`` chooses between."""
    return _SYSTEM_PAIR


def resolve_palette(name) -> Palette:
    """Resolve a palette *name* to a concrete :class:`Palette`.

    ``"system"`` consults the OS light/dark preference.  An unknown or ``None``
    name falls back to the app default, then to :data:`LIGHT` — it never
    raises, because a stale stored value must not stop a window opening.
    """
    if name is None or str(name).lower() == "system":
        from VIStk.Styles._system import os_scheme
        light, dark = _SYSTEM_PAIR
        name = dark if os_scheme() == "dark" else light
    return get_palette(name) or get_palette(_DEFAULT) or LIGHT


def base_palette(scheme) -> Palette:
    """The pre-registry spelling of :func:`resolve_palette`."""
    return resolve_palette(scheme)


register_palette("light", LIGHT, base=None)
register_palette("dark", DARK, base=None)


# ── Shading ────────────────────────────────────────────────────────────────

def _rgb(color):
    """Resolve *color* to an ``(r, g, b)`` 0-255 tuple, or ``None``.

    Understands hex (``#rgb`` / ``#rrggbb`` / ``#rrrrggggbbbb``) and the
    ``greyNN`` / ``grayNN`` names directly, so it works before a Tk root
    exists — ``Screens/styles.py`` runs before the first window opens.  Any
    other Tk colour name goes through the default root when there is one, and
    otherwise gives up (the caller then leaves the colour alone).
    """
    text = str(color).strip()
    if text.startswith("#"):
        digits = text[1:]
        width, rem = divmod(len(digits), 3)
        if rem or width not in (1, 2, 4):
            return None
        try:
            parts = [int(digits[i * width:(i + 1) * width], 16) for i in range(3)]
        except ValueError:
            return None
        if width == 1:
            return tuple(p * 17 for p in parts)
        if width == 4:
            return tuple(p // 257 for p in parts)
        return tuple(parts)
    low = text.lower()
    for name in ("grey", "gray"):
        if low.startswith(name) and low[len(name):].isdigit():
            level = round(min(100, int(low[len(name):])) * 255 / 100)
            return (level, level, level)
    try:
        import tkinter
        root = tkinter._default_root
        if root is not None:
            r, g, b = root.winfo_rgb(text)
            return (r // 256, g // 256, b // 256)
    except Exception:
        pass
    return None


def _hex(rgb) -> str:
    return "#%02x%02x%02x" % tuple(max(0, min(255, round(c))) for c in rgb)


def dim(color, amount: float) -> str:
    """*color* darkened by *amount* (0..1), or lightened if it is near-black.

    Near-black colours have no room to darken, so the shift flips direction to
    keep the two distinguishable.  Returns ``str(color)`` unchanged when the
    colour can't be resolved.
    """
    rgb = _rgb(color)
    if rgb is None:
        return str(color)
    if max(rgb) < 32:
        return lift(color, amount)
    return _hex(tuple(c * (1 - amount) for c in rgb))


def lift(color, amount: float) -> str:
    """*color* lightened by *amount* (0..1), or darkened if it is near-white."""
    rgb = _rgb(color)
    if rgb is None:
        return str(color)
    if min(rgb) > 223:
        return _hex(tuple(c * (1 - amount) for c in rgb))
    return _hex(tuple(c + (255 - c) * amount for c in rgb))


def bar_companions(bar, skip=frozenset()) -> dict:
    """The bar's own state colours, shaded from the strip background.

    Returns ``focused`` / ``unfocused`` / ``empty`` / ``empty_hover`` — what
    the strip paints in each state — minus anything named in *skip*, so an
    explicit value always wins.  The shifts reproduce the relationships the
    shipped palettes use (empty slightly dimmer than the bar, the drag
    highlight brighter, an unfocused pane dimmer still).
    """
    derived = {
        "focused": str(bar),
        "unfocused": dim(bar, 0.16),
        "empty": dim(bar, 0.07),
        "empty_hover": lift(bar, 0.12),
    }
    return {role: value for role, value in derived.items() if role not in skip}
