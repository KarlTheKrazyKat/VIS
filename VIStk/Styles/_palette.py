"""Palette — the named colour *roles* the VIStk chrome paints with.

A :class:`Palette` is a flat, immutable set of colour roles covering the whole
window chrome (tab bar today; ``InfoRow`` follows).  Widgets read
``style.palette.<role>`` instead of hardcoding a colour, so the same widget can
wear any scheme.  :data:`LIGHT` reproduces the exact greys the widgets used
before the styles system existed — so the ``classic`` tab style renders
byte-for-byte identically to the pre-styles build.

Two orthogonal axes drive the final look:

* **scheme** (:data:`LIGHT` / :data:`DARK`) — the base neutral palette, chosen
  by the ``appearance.color_scheme`` setting.
* **tab style** (:mod:`VIStk.Styles._tabstyle`) — the shape/indicator variant,
  which may also override individual roles on top of the scheme base.
"""
from __future__ import annotations

from dataclasses import dataclass, replace

__all__ = ["Palette", "LIGHT", "DARK", "base_palette"]


@dataclass(frozen=True)
class Palette:
    """Named colour roles for the window chrome.

    Every field is a Tk colour string (a name like ``"grey62"`` or a hex
    ``"#2b2b2b"``).  Frozen so a palette can be shared freely; derive a variant
    with :func:`dataclasses.replace`.
    """

    # ── Tab bar ────────────────────────────────────────────────────────────
    bar_bg: str            #: tab strip background
    tab_active: str        #: selected tab (and its close button)
    tab_inactive: str      #: unselected tab (usually == bar_bg)
    tab_hover: str         #: hover over an unselected tab
    close_hover: str       #: hover over any close button
    separator: str         #: vertical/horizontal divider between tabs
    accent: str            #: active-tab indicator + drag insertion line
    empty: str             #: empty-bar resting drop-zone colour
    empty_hover: str       #: empty-bar highlight during a drag hover
    focused: str           #: strip when its pane is focused (usually == bar_bg)
    unfocused: str         #: strip when its pane is NOT focused (dimmer)
    active_unfocused: str  #: active tab in an unfocused pane
    tab_drag: str          #: the dragged tab while its ghost is live
    tab_fg: str            #: tab label colour
    tab_active_fg: str     #: active tab label colour

    # ── Info row (status bar) — consumed in a follow-up ────────────────────
    info_bg: str           #: status-bar background
    info_fg: str           #: status-bar text


#: The pre-styles greys, exactly.  ``classic`` on ``LIGHT`` == the old build.
LIGHT = Palette(
    bar_bg="grey62",
    tab_active="grey85",
    tab_inactive="grey62",
    tab_hover="grey72",
    close_hover="IndianRed",
    separator="grey50",
    accent="dodger blue",
    empty="grey55",
    empty_hover="grey68",
    focused="grey62",
    unfocused="grey52",
    active_unfocused="grey65",
    tab_drag="grey45",
    tab_fg="black",
    tab_active_fg="black",
    info_bg="grey55",
    info_fg="grey88",
)

#: A dark neutral scheme.  Styled presets that bring their own accent layer on
#: top of this; ``classic``/``minimal`` mostly just swap the greys.
DARK = Palette(
    bar_bg="grey25",
    tab_active="grey38",
    tab_inactive="grey25",
    tab_hover="grey32",
    close_hover="IndianRed",
    separator="grey40",
    accent="#4aa3ff",
    empty="grey22",
    empty_hover="grey30",
    focused="grey25",
    unfocused="grey18",
    active_unfocused="grey30",
    tab_drag="grey15",
    tab_fg="grey90",
    tab_active_fg="white",
    info_bg="grey20",
    info_fg="grey70",
)

_SCHEMES = {"light": LIGHT, "dark": DARK}


def base_palette(scheme: str | None) -> Palette:
    """Return the base :class:`Palette` for a scheme name.

    ``"dark"`` → :data:`DARK`; anything else (including ``"system"`` and
    ``None``) → :data:`LIGHT`.  The ``system`` value is treated as light until
    OS-theme detection lands — it must never raise.
    """
    return _SCHEMES.get((scheme or "light").lower(), LIGHT)
