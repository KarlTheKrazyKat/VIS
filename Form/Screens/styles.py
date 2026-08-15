"""Application styling — tab shapes and colour palettes.

Imported once at startup by ``.VIS/Host.py`` (before the first window opens).
Use it to curate what the user can pick in **Settings → Appearance**, and,
optionally, to author your own looks.

A **tab style** is the shape (``appearance.tab_style``); a **palette** is the
colour (``appearance.color_scheme``).  They compose, so any style renders in
any palette.  Both choices are stored in ``.VIS/settings.json``; this file
defines the menus and the defaults.

Built-in styles: ``classic`` (the default grey look), ``underline``,
``topline``, ``pill``.  Built-in palettes: ``light``, ``dark``.
"""
from VIStk.Widgets import TabBar
from VIStk.Structures._Project import Project
from VIStk.Styles import TabStyle          # noqa: F401  (authoring a style)
from VIStk.Styles import Palette           # noqa: F401  (authoring a palette)

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

# ── Author a colour palette (optional) ──────────────────────────────────────
# A palette is an open name -> colour mapping.  The names are yours; widgets
# refer to them where a colour is expected:  Label(f, bg="page", fg="muted").
# Names you leave out fall through to `base`, so keep it as short as you like.
# The tab bar is not special — it reads bar_bg / tab_active / tab_fg out of the
# same mapping, so naming those restyles the chrome.
#
# Project.registerPalette("corporate light", {
#     "page":   "#f3f6f8",
#     "card":   "#ffffff",
#     "ink":    "#1a1a1a",
#     "muted":  "#6b6b6b",
#     "accent": "#00a86b",
#     "bar_bg": "#f7f8fa",
# })
# Project.registerPalette("corporate dark", {
#     "page":   "#242424",
#     "card":   "#333333",
#     "ink":    "#e6e6e6",
#     "muted":  "#9a9a9a",
#     "accent": "#00a86b",
#     "bar_bg": "#2b2b2b",
# }, base="dark")
#
# Project.offerPalettes(["corporate light", "corporate dark"],
#                       default="corporate light")
# Project.setSystemPalettes("corporate light", "corporate dark")

# ── Widget colours ──────────────────────────────────────────────────────────
# Screens name palette colours instead of hardcoding them:
#
#     v_label = Label(f_cc, text="Part", bg="page", fg="muted")
#
# A "#rrggbb" literal is passed straight through and never repainted; any other
# string is looked up in the palette.  Switching palettes re-resolves the names.
#
# The ttk base theme is your call.  The platform default (Windows "vista")
# draws Buttons, Entries, Comboboxes, Notebook tabs and Scrollbars natively —
# they keep the native look and ignore palette colours, while ttk Frames and
# Labels still follow it.  A Tk-drawn theme hands every ttk control to the
# palette instead.  Classic tk widgets follow it either way.
#
# Project.setWidgetTheme("clam")     # palette reaches every ttk control

# ── Curate the menus ────────────────────────────────────────────────────────
# The ordered lists the user chooses from, and the defaults when nothing is
# saved.  Remove a call entirely to offer everything registered.
TabBar.offer_styles(
    ["classic", "underline", "topline", "pill"],
    default="classic",
)

Project.offerPalettes(["light", "dark"], default="light")
