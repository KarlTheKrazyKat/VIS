"""VIStk styling system — palettes and tab-bar style presets.

The chrome (tab bar, ``InfoRow``) and, increasingly, the general UI read their
colours from a :class:`~VIStk.Styles._palette.Palette` chosen by two orthogonal
axes:

* **palette** — a registered set of colour roles, from
  ``appearance.color_scheme``.  Two ship (``light`` / ``dark``); apps register
  their own and curate which the Settings window offers.  ``"system"`` follows
  the OS light/dark preference.
* **tab style** — a :class:`~VIStk.Styles._tabstyle.TabStyle` preset (four ship;
  apps add more), from ``appearance.tab_style``.

Apps do not call into this module directly.  Palettes are registered and
curated on :class:`~VIStk.Structures._Project.Project`, which already owns the
``Settings`` the user's pick is stored in, from ``Screens/styles.py``::

    from VIStk.Structures._Project import Project
    from VIStk.Styles import Palette

    Project.registerPalette("bmi Light", Palette.from_preset(
        "light", bar_bg="#f7f8fa", accent="#0a6cff"))
    Project.offerPalettes(["bmi Light", "bmi Dark", "light", "dark"],
                          default="bmi Light")

Tab *styles* are curated on :class:`~VIStk.Widgets.TabBar`
(``register_tab_style`` / ``offer_styles`` / ``setStyle``), which also owns the
palette *repaint* methods (``setDefaultPalette`` / ``setActivePalette``).  The
module-level functions below are the registry those front doors delegate to —
framework-internal, not the app-facing spelling.
"""
from VIStk.Styles._palette import (
    Palette, LIGHT, DARK, base_palette, dim, lift, bar_companions,
    register_palette, get_palette, palette_names, offer_palettes,
    offered_palettes, default_palette, set_default_palette,
    set_system_palettes, system_palettes, resolve_palette,
)
from VIStk.Styles._system import os_scheme
from VIStk.Styles._tabstyle import (
    TabStyle, ResolvedStyle, register, get, names, resolve, DEFAULT,
)

__all__ = [
    "Palette", "LIGHT", "DARK", "base_palette", "dim", "lift", "bar_companions",
    "register_palette", "get_palette", "palette_names", "offer_palettes",
    "offered_palettes", "default_palette", "set_default_palette",
    "set_system_palettes", "system_palettes", "resolve_palette", "os_scheme",
    "TabStyle", "ResolvedStyle", "register", "get", "names", "resolve",
    "DEFAULT",
]
