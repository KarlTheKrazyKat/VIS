"""TabStyle — a named tab-bar look, plus the registry the Settings menu reads.

A :class:`TabStyle` is a *recipe*, not concrete colours: an indicator variant
(``none`` / ``underline`` / ``topline``), whether tabs are separated, a corner
radius, and an optional set of palette *overrides* layered on top of the active
scheme.  :func:`resolve` turns ``(scheme, style_name)`` into a
:class:`ResolvedStyle` — a concrete :class:`~VIStk.Styles._palette.Palette`
plus the flags — which is what a :class:`~VIStk.Widgets.TabBar` actually paints.

Four presets ship: ``classic`` (the pre-styles look), ``underline``,
``topline``, and ``pill``.  Apps author more with
:meth:`TabStyle.from_preset` and register them via
:meth:`VIStk.Widgets.TabBar.register_tab_style` (typically from
``Screens/styles.py``).

Overrides may reference another *resolved* role with a ``"$role"`` string
(e.g. ``tab_active="$bar_bg"`` makes the active tab flat in whatever scheme is
active).  ``$``-refs resolve after literal overrides, against the updated
palette, so a style stays scheme-aware without hardcoding greys.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace

from VIStk.Styles._palette import Palette, base_palette

__all__ = ["TabStyle", "ResolvedStyle", "register", "get", "names",
           "resolve", "DEFAULT"]

_INDICATORS = ("none", "underline", "topline")


@dataclass(frozen=True)
class TabStyle:
    """A tab-bar look recipe.

    Args:
        indicator:  Active-tab marker — ``"none"`` (distinguished by fill only,
                    like ``classic``), ``"underline"`` (accent bar along the
                    trailing edge), or ``"topline"`` (accent bar on the leading
                    edge).
        separators: Draw dividers between tabs.
        radius:     Corner radius in px; ``> 0`` renders tabs as rounded
                    ``vButton`` pills.  ``0`` uses plain buttons.
        overrides:  Partial ``role -> colour`` map layered on the scheme
                    palette.  A ``"$role"`` value copies another resolved role.
        accent:     Shortcut for ``overrides["accent"]`` (the indicator/pill
                    colour); ``None`` keeps the scheme accent.
    """

    indicator: str = "none"
    separators: bool = True
    radius: int = 0
    overrides: dict = field(default_factory=dict)
    accent: str | None = None

    def __post_init__(self):
        if self.indicator not in _INDICATORS:
            raise ValueError(
                f"indicator must be one of {_INDICATORS}, got {self.indicator!r}")

    @classmethod
    def from_preset(cls, base: str, *, accent: str | None = None,
                    palette: dict | None = None, indicator: str | None = None,
                    separators: bool | None = None,
                    radius: int | None = None) -> "TabStyle":
        """Derive a new style from a registered preset, overriding only what
        you pass.  ``palette`` is merged onto the preset's own overrides."""
        b = _REGISTRY.get(base) or _REGISTRY["classic"]
        ov = dict(b.overrides)
        if palette:
            ov.update(palette)
        return cls(
            indicator=b.indicator if indicator is None else indicator,
            separators=b.separators if separators is None else separators,
            radius=b.radius if radius is None else radius,
            overrides=ov,
            accent=b.accent if accent is None else accent,
        )


@dataclass(frozen=True)
class ResolvedStyle:
    """A concrete style: a fully-resolved palette plus the render flags.

    This is what a :class:`~VIStk.Widgets.TabBar` reads.  Produced by
    :func:`resolve`; never constructed by callers directly.
    """

    palette: Palette
    indicator: str
    separators: bool
    radius: int


# ── Registry ───────────────────────────────────────────────────────────────
# Insertion-ordered so the Settings menu can offer styles in a stable order.
_REGISTRY: dict[str, TabStyle] = {}
_ORDER: list[str] = []


def register(name: str, style: TabStyle) -> None:
    """Add or replace *name* in the registry (re-registering keeps its slot)."""
    if not isinstance(style, TabStyle):
        raise TypeError(f"style must be a TabStyle, got {type(style).__name__}")
    if name not in _REGISTRY:
        _ORDER.append(name)
    _REGISTRY[name] = style


def get(name: str) -> TabStyle | None:
    """Return the registered :class:`TabStyle` for *name*, or ``None``."""
    return _REGISTRY.get(name)


def names() -> list[str]:
    """Every registered style name, in registration order."""
    return list(_ORDER)


def resolve(scheme: str | None, style_name: str | None) -> ResolvedStyle:
    """Resolve ``(scheme, style_name)`` into a concrete :class:`ResolvedStyle`.

    Falls back to ``classic`` for an unknown/None style name and to the light
    scheme for an unknown/None scheme, so it never raises on bad input.
    """
    style = _REGISTRY.get(style_name) or _REGISTRY["classic"]
    pal = base_palette(scheme)

    ov = dict(style.overrides)
    if style.accent is not None:
        ov["accent"] = style.accent

    # Literal overrides first, then "$role" references against the updated
    # palette, so a ref sees any literal it depends on.
    literal = {k: v for k, v in ov.items()
               if hasattr(pal, k) and not (isinstance(v, str) and v.startswith("$"))}
    if literal:
        pal = replace(pal, **literal)
    refs = {k: getattr(pal, v[1:]) for k, v in ov.items()
            if isinstance(v, str) and v.startswith("$")
            and hasattr(pal, k) and hasattr(pal, v[1:])}
    if refs:
        pal = replace(pal, **refs)

    return ResolvedStyle(palette=pal, indicator=style.indicator,
                         separators=style.separators, radius=style.radius)


# ── Built-in presets ─────────────────────────────────────────────────────────
# classic MUST leave the scheme palette untouched (no overrides, no indicator,
# separators on) so `classic` on LIGHT == the pre-styles look, exactly.
register("classic", TabStyle())

# Flat tabs, active marked by an accent bar under it. Active fill == bar so the
# only cue is the underline; hover still lifts to tab_hover.
register("underline", TabStyle(
    indicator="underline", separators=False,
    overrides={"tab_active": "$bar_bg", "tab_active_fg": "$tab_fg"}))

# Like classic (active tab keeps its lighter fill) but the marker is a bar on
# the leading edge instead of a fill-only cue, and no dividers.
register("topline", TabStyle(indicator="topline", separators=False))

# Rounded pills: active filled with the accent, inactive muted, no dividers.
register("pill", TabStyle(
    radius=10, separators=False,
    overrides={"tab_active": "$accent", "tab_active_fg": "white",
               "tab_inactive": "grey72", "tab_hover": "grey78",
               "active_unfocused": "grey78"}))

#: The launch fallback before the Host resolves settings — classic on light.
DEFAULT = resolve("light", "classic")
