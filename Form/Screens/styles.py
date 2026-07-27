"""Application tab styling.

Imported once at startup by ``.VIS/Host.py`` (before the first window opens).
Use it to curate which tab looks the user can pick in
**Settings → Appearance → Tab style**, and, optionally, to author your own.

Built-in styles: ``classic`` (the default grey look), ``underline``,
``topline``, ``pill``, and ``minimal``.  The user's choice is stored in
``.VIS/settings.json`` (``appearance.tab_style``); this file only defines the
menu and the default.
"""
from VIStk.Widgets import TabBar
from VIStk.Styles import TabStyle  # noqa: F401  (used when authoring a style)

# ── Author a custom look (optional) ─────────────────────────────────────────
# Start from a built-in preset and override only what you want.  Add the name
# to offer_styles() below to expose it to the user.
#
# TabBar.register_tab_style(
#     "corporate",
#     TabStyle.from_preset(
#         "underline",
#         accent="#00a86b",
#         palette={"bar_bg": "#2b2b2b", "tab_active": "#3a3a3a"},
#     ),
# )

# ── Curate the menu ─────────────────────────────────────────────────────────
# The ordered list the user chooses from, and the default when none is saved.
# Remove this call entirely to offer every registered style with the "classic"
# default.
TabBar.offer_styles(
    ["classic", "underline", "topline", "pill", "minimal"],
    default="classic",
)
