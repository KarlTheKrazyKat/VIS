"""VIStk styling system — palettes and tab-bar style presets.

The chrome (tab bar today, ``InfoRow`` next) reads its colours from a
:class:`~VIStk.Styles._palette.Palette` chosen by two orthogonal axes:

* **scheme** — :data:`LIGHT` / :data:`DARK`, from ``appearance.color_scheme``.
* **tab style** — a :class:`~VIStk.Styles._tabstyle.TabStyle` preset (five ship;
  apps add more), from ``appearance.tab_style``.

Apps normally touch this only through :class:`~VIStk.Widgets.TabBar`'s
classmethods (``register_tab_style`` / ``offer_styles``), typically from
``Screens/styles.py``.  The names below are the lower-level API those delegate
to.
"""
from VIStk.Styles._palette import Palette, LIGHT, DARK, base_palette
from VIStk.Styles._tabstyle import (
    TabStyle, ResolvedStyle, register, get, names, resolve, DEFAULT,
)

__all__ = [
    "Palette", "LIGHT", "DARK", "base_palette",
    "TabStyle", "ResolvedStyle", "register", "get", "names", "resolve",
    "DEFAULT",
]
