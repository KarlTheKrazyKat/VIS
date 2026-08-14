from tkinter import Frame, Button, Label, Menu, Toplevel, TclError

from VIStk.Styles import resolve as _resolve_style, names as _style_names
from VIStk.Styles._tabstyle import DEFAULT as _DEFAULT_STYLE

# ── Non-colour geometry constants ──────────────────────────────────────────────
# All colours now come from the active ``ResolvedStyle`` (see VIStk.Styles);
# the ``classic`` style on the light scheme reproduces the historical greys.
_DRAG_THRESHOLD  = 8           # pixels of motion (any direction) to activate drag ghost
_EMPTY_BAR_H     = 28          # height of the bar when no tabs are open (horizontal)
_EMPTY_BAR_W     = 28          # width of the bar when no tabs are open (vertical)

# Tab geometry — the label/close sit in a content-sized tab that fills the bar
# height and butts flush against its neighbours (dividers come from separators
# or the inter-tab gap, per style).  ``_TAB_PADX``/``_TAB_PADY`` are the label's
# internal padding; the close carries its own small pad and a larger ✕ glyph.
_TAB_PADX        = 7           # internal L/R padding of the tab label
_TAB_PADY        = 4           # internal T/B padding — gives the bar its height
_CLOSE_PADX      = 2           # internal L/R padding of the close button
_CLOSE_FONT      = ("Segoe UI", 11)   # slightly larger ✕ than the label font

# Pill style: a tab floats in the bar as a single rounded capsule.  The label
# and close are separate widgets, so the capsule is formed by rounding only the
# label's left end and only the close's right end (same fill, abutting).  A pill
# tab is inset vertically (float) and gapped horizontally (from the bar edge and
# between pills); a flush, full-height tab has neither.
_PILL_PADY       = 3           # T/B inset so the capsule floats in the bar
_PILL_GAP        = 6           # gap at the bar's left edge and between pills
# The capsule ends are full semicircles (radius = half the height), so the label
# text and the ✕ must be padded clear of them, and the close must be wide enough
# to actually show a full-height semicircle (else its cap is a smaller radius
# than the label's).  These pill paddings are larger than the flat-tab ones.
_PILL_LABEL_PADX = 6           # a little space left of the label text
_PILL_CLOSE_PADX = 9           # keeps the ✕ off the right cap and widens the cap
# Per-corner rounding order is (top_left, top_right, bottom_right, bottom_left).
_PILL_LEFT       = (True, False, False, True)    # label: round the left end
_PILL_RIGHT      = (False, True, True, False)    # close: round the right end

# ── Global registry ───────────────────────────────────────────────────────────
# All live TabBar instances register here so cross-bar detection works — and so
# a live tab-style change can be broadcast to every open bar (set_tab_style).
_TABBAR_REGISTRY: list["TabBar"] = []


class TabBar(Frame):
    """A row of clickable tabs displayed at the top of a ``TabManager``.

    Keyed by tab ID (0.4.7): every tab opened via ``open_tab(tab_id, label,
    ...)`` is tracked by a stable integer allocated by the owning
    ``TabManager``.  Display labels are mutable (``update_tab_label``) and
    may collide with labels in other bars — IDs disambiguate.

    During a drag a semi-transparent ghost Toplevel follows the cursor.  Tabs
    do not slide until the mouse is released.  A coloured insertion indicator
    appears in the hovered bar.  On release: reorder in the same bar / merge
    into another bar / detach if the cursor is outside all bars.

    When no tabs are open the bar shrinks to a visible drop-zone strip.
    Drags hovering over an empty bar expand and highlight it.

    Right-click: "Open in new window", "Force refresh", "Close".

    **Styling (0.6.x).**  Colours and the tab shape come from a
    :class:`~VIStk.Styles.ResolvedStyle`, not hardcoded greys.  The active
    style is process-wide class state: :meth:`set_tab_style` resolves a named
    style against the current scheme and pushes it to every live bar.  Apps
    author looks with :meth:`register_tab_style` and choose which the user may
    pick with :meth:`offer_styles` (typically from ``Screens/styles.py``).  The
    ``classic`` style on the light scheme is identical to the pre-styles look.

    Attributes:
        active            (int | None)            tab ID of the active tab
        owner             (TabManager | None)     set by TabManager after init
        style             (ResolvedStyle)         the bar's current resolved style
        on_focus_change   (callable | None)       ``(tab_id: int | None)``
        on_tab_close      (callable | None)       ``(tab_id: int)``
        on_tab_popout     (callable | None)       ``(tab_id: int)``
        on_tab_refresh    (callable | None)       ``(tab_id: int)``
        on_drag_detach    (callable | None)       ``(tab_id: int)``
        on_drag_merge     (callable | None)       ``(tab_id: int, source: TabBar, idx: int)``
        on_tab_split      (callable | None)       ``(tab_id: int, direction: str, pane)``

    After every drag ends ``_last_drag_btn_offset_x`` / ``_last_drag_btn_offset_y``
    hold the cursor's pixel offset within the dragged tab button.  External
    code (e.g. Host) may read these to position a new DetachedWindow.
    """

    # ── Process-wide style state ───────────────────────────────────────────────
    #: The resolved style every new/live bar paints with.  Set by
    #: :meth:`set_tab_style`; falls back to ``classic`` on light before the Host
    #: resolves settings.
    _active_style = _DEFAULT_STYLE
    _active_scheme: str = "light"
    #: Name of the base style currently resolved (so palette overrides can be
    #: re-applied after a re-resolve).  ``None`` when set from a raw ResolvedStyle.
    _active_style_name: "str | None" = "classic"
    #: Sticky ``role -> colour`` overrides from :meth:`setPalette`, re-applied on
    #: top of every resolved style so an app's custom colours survive a style
    #: switch and the Host applying the user's saved pick at launch.
    _palette_overrides: dict = {}
    #: App-curated subset of style names offered in the Settings menu; ``None``
    #: means "every registered style".  Set via :meth:`offer_styles`.
    _offered: "list[str] | None" = None
    #: Fallback style name when the user's saved pick is unknown/unset.
    _default_style: str = "classic"

    def __init__(self, parent, position: str = "top", **kwargs):
        self.style = TabBar._active_style
        kwargs.setdefault("bg", self.style.palette.bar_bg)
        super().__init__(parent, **kwargs)
        self._tabs: dict[int, dict] = {}
        """tab_id -> {"label": str, "button": Button, "close": Button, "sep": Frame|None, "icon": image|None}"""
        self.active: int | None = None
        self.owner = None               # set by TabManager
        self._position: str = position  # "top" | "bottom" | "left" | "right"

        # Callbacks
        self.on_focus_change = None
        self.on_tab_close    = None
        self.on_tab_popout   = None
        self.on_tab_refresh  = None
        self.on_drag_detach  = None
        self.on_drag_merge   = None     # (tab_id, source_bar, insert_idx)
        self.on_tab_split    = None     # (tab_id, direction, pane=None)
        self.on_drag_zone    = None     # (x_root, y_root) -> (pane, direction) | None
        self._focused: bool  = True     # visual focused state (set by set_focused_style)

        # Drag state
        self._drag_id: int | None = None
        self._drag_start_x: int = 0
        self._drag_start_y: int = 0
        self._drag_btn_offset_x: int = 0    # cursor x relative to tab button left
        self._drag_btn_offset_y: int = 0    # cursor y relative to tab button top
        self._drag_active: bool = False

        # Persisted after drag so Host can read them for DetachedWindow positioning
        self._last_drag_btn_offset_x: int = 0
        self._last_drag_btn_offset_y: int = 0

        # Ghost window (follows cursor during drag)
        self._ghost: Toplevel | None = None

        # Insertion indicator (owned by this bar, placed during drag hover)
        self._insert_indicator: Frame | None = None

        # Active-tab style indicator (underline / topline accent bar)
        self._active_indicator: Frame | None = None

        # Cross-bar tracking (owned by the dragging bar)
        self._insert_bar: "TabBar | None" = None
        self._insert_idx: int = -1

        # Natural populated size, captured once and reused for the empty state
        # so 0->1 transitions don't grow the bar by a few pixels.
        self._natural_height: int = 0
        self._natural_width: int = 0

        _TABBAR_REGISTRY.append(self)
        self._update_empty_state()
        # Re-place the active indicator once the bar is actually laid out; the
        # first placement is scheduled before launch geometry settles (below).
        self.bind("<Configure>", self._on_configure)

    # ── Style: class-level API (app-facing) ─────────────────────────────────────

    @classmethod
    def register_tab_style(cls, name: str, style) -> None:
        """Register (or replace) a tab-style preset named *name*.

        *style* is a :class:`VIStk.Styles.TabStyle` — usually built with
        :meth:`TabStyle.from_preset`.  Call from ``Screens/styles.py`` so the
        look is available before any window opens::

            from VIStk.Widgets import TabBar
            from VIStk.Styles import TabStyle
            TabBar.register_tab_style(
                "corporate",
                TabStyle.from_preset("underline", accent="#00a86b"))
        """
        from VIStk.Styles import register
        register(name, style)

    @classmethod
    def offer_styles(cls, names, default: "str | None" = None) -> None:
        """Curate which style names the Settings menu offers the user.

        *names* is the ordered list shown in the appearance dropdown; pass
        *default* to also set the fallback used when no valid pick is stored.
        Call with no styles system touched at all and the menu offers every
        registered style with ``classic`` as the default.
        """
        cls._offered = list(names)
        if default is not None:
            cls._default_style = default

    @classmethod
    def offered_styles(cls) -> "list[str]":
        """The style names the Settings menu should offer (curated or all)."""
        return list(cls._offered) if cls._offered is not None else _style_names()

    @classmethod
    def default_style(cls) -> str:
        """The fallback style name (set via :meth:`offer_styles`)."""
        return cls._default_style

    @classmethod
    def set_tab_style(cls, style, scheme: "str | None" = None) -> None:
        """Make *style* the active tab style for every open and future bar.

        *style* may be a registered style **name** or an already-resolved
        :class:`~VIStk.Styles.ResolvedStyle`.  *scheme* defaults to the last
        scheme set here.  Applies live to every bar in the registry.
        """
        from VIStk.Styles import ResolvedStyle
        if scheme is not None:
            cls._active_scheme = scheme
        if isinstance(style, ResolvedStyle):
            resolved = style
        else:
            cls._active_style_name = style
            resolved = _resolve_style(cls._active_scheme, style)
        # Re-apply any sticky setPalette() overrides on top of the resolved
        # style, so app colours survive a style switch / the Host's launch pick.
        if cls._palette_overrides:
            from dataclasses import replace
            resolved = ResolvedStyle(
                palette=replace(resolved.palette, **cls._palette_overrides),
                indicator=resolved.indicator, separators=resolved.separators,
                radius=resolved.radius)
        cls._active_style = resolved
        for bar in list(_TABBAR_REGISTRY):
            try:
                bar.apply_style(resolved)
            except TclError:
                pass

    @classmethod
    def setStyle(cls, name: str) -> None:
        """Switch every tab bar to one of the built-in styles by name.

        *name* is one of the shipped presets — ``"classic"``, ``"underline"``,
        ``"topline"`` or ``"pill"`` (or any style registered via
        :meth:`register_tab_style`).  Applies live to every open bar and becomes
        the style for new ones.  Raises ``ValueError`` for an unknown name.
        """
        from VIStk.Styles import get
        if get(name) is None:
            raise ValueError(
                f"Unknown tab style {name!r}; choose from {_style_names()}")
        cls.set_tab_style(name)

    @classmethod
    def setPalette(cls, *, bar: "str | None" = None, tab: "str | None" = None,
                   selected: "str | None" = None, text: "str | None" = None,
                   close: "str | None" = None,
                   selected_text: "str | None" = None) -> None:
        """Recolour the active tab style, live, on every bar.

        Each argument is a Tk colour (a name like ``"grey62"`` or a hex
        ``"#1e90ff"``); omitted arguments keep their current colour.  The
        overrides are **sticky**: they are stored and re-applied on top of every
        resolved style, so they survive a later :meth:`setStyle` and the Host
        applying the user's saved pick at launch.  Call with no arguments and
        nothing changes.

        Args:
            bar:            The tab-strip background.
            tab:            An unselected tab.
            selected:       The selected tab.
            text:           Label + ✕ colour, on every tab (also the selected
                            tab unless *selected_text* is given).
            close:          The ✕ close-button highlight (hover / press).
            selected_text:  Label + ✕ colour on the selected tab only.
        """
        changes: dict = {}
        if bar is not None:
            changes["bar_bg"] = bar
            changes["focused"] = bar
        if tab is not None:
            changes["tab_inactive"] = tab
        if selected is not None:
            changes["tab_active"] = selected
        if text is not None:
            changes["tab_fg"] = text
            changes.setdefault("tab_active_fg", text)
        if selected_text is not None:
            changes["tab_active_fg"] = selected_text
        if close is not None:
            changes["close_hover"] = close
        if not changes:
            return
        cls._palette_overrides = {**cls._palette_overrides, **changes}
        # Re-resolve the current base style; set_tab_style layers the overrides.
        cls.set_tab_style(cls._active_style_name or cls._active_style)

    @property
    def _pal(self):
        """Shorthand for the active palette."""
        return self.style.palette

    # ── Position helpers ───────────────────────────────────────────────────────

    def _is_vertical(self) -> bool:
        """Return True when the bar is oriented for left/right placement."""
        return self._position in ("left", "right")

    def set_position(self, position: str):
        """Change tab bar position. Called by TabManager when layout changes."""
        self._position = position
        # Repack all tabs under the new orientation
        ids = list(self._tabs.keys())
        self._rebuild_packing(ids)
        self._update_empty_state()

    def get_accessory(self):
        """Right-aligned container at the trailing edge of a *horizontal* bar.

        Lazily created and packed ``side="right"`` so it stays pinned to the
        strip's right corner no matter how many tabs are added: tabs pack from
        the left, and ``_rebuild_packing`` only forgets/repacks widgets tracked
        in ``self._tabs`` — this frame is not one of them, so it is never
        disturbed.  Returns ``None`` for vertical (left/right) bars, which have
        no top-right corner that reads as a menubar accessory slot.

        Host uses this to mount app-registered menubar accessories (e.g. a
        current-user badge) since the native OS menubar can't host widgets.
        """
        if self._is_vertical():
            return None
        acc = getattr(self, "_accessory", None)
        if acc is None or not acc.winfo_exists():
            acc = Frame(self, bg=self._pal.bar_bg)
            acc.pack(side="right", fill="y", padx=(0, 6))
            self._accessory = acc
        return acc

    # ── Public API ─────────────────────────────────────────────────────────────

    def open_tab(self, tab_id: int, label: str, icon=None,
                 insert_idx: int = -1) -> bool:
        """Add a tab button identified by *tab_id* with text *label*.

        Args:
            tab_id:     Stable integer ID allocated by the owning TabManager.
            label:      Text shown on the tab button.
            icon:       Optional ``PIL.ImageTk.PhotoImage`` shown left of label.
            insert_idx: 0-based position to insert at; -1 appends.

        Returns:
            ``True`` if a new tab was created, ``False`` if *tab_id* already existed.
        """
        if tab_id in self._tabs:
            return False

        first = not self._tabs
        sep = self._make_separator() if self._tabs else None

        btn = self._make_tab_button(tab_id, label, icon)
        close_btn = self._make_close_button(tab_id)
        self._pack_tab(btn, close_btn, first=first)

        btn.bind("<ButtonPress-1>",   lambda e, i=tab_id: self._on_drag_start(e, i))
        btn.bind("<B1-Motion>",       lambda e, i=tab_id: self._on_drag_motion(e, i))
        btn.bind("<ButtonRelease-1>", lambda e: self._on_drag_release(e))
        btn.bind("<Button-3>",        lambda e, i=tab_id: self._on_right_click(e, i))

        btn.bind("<Enter>",       lambda e, i=tab_id: self._on_tab_enter(i))
        btn.bind("<Leave>",       lambda e, i=tab_id: self._on_tab_leave(i))
        close_btn.bind("<Enter>", lambda e, i=tab_id: self._on_close_enter(i))
        close_btn.bind("<Leave>", lambda e, i=tab_id: self._on_close_leave(i))

        self._tabs[tab_id] = {
            "label": label, "button": btn, "close": close_btn,
            "sep": sep, "icon": icon,
        }
        self.focus_tab(tab_id)

        if insert_idx >= 0:
            ids = list(self._tabs.keys())
            if tab_id in ids and len(ids) > 1:
                self._reorder_to_idx(tab_id, insert_idx)

        self._update_empty_state()
        return True

    def close_tab(self, tab_id: int) -> bool:
        """Remove the tab identified by *tab_id*.

        If the first tab is closed, the new first tab's orphaned separator is
        also removed.

        Returns:
            ``True`` if removed, ``False`` if not found.
        """
        if tab_id not in self._tabs:
            return False

        ids = list(self._tabs.keys())
        tab_idx = ids.index(tab_id)

        if self._tabs[tab_id]["sep"]:
            self._tabs[tab_id]["sep"].destroy()
        self._tabs[tab_id]["button"].destroy()
        self._tabs[tab_id]["close"].destroy()
        del self._tabs[tab_id]

        if tab_idx == 0 and self._tabs:
            new_first = next(iter(self._tabs))
            if self._tabs[new_first]["sep"]:
                self._tabs[new_first]["sep"].destroy()
                self._tabs[new_first]["sep"] = None

        if self.active == tab_id:
            self.active = None
            remaining = list(self._tabs.keys())
            if remaining:
                self.focus_tab(remaining[-1])
            elif self.on_focus_change:
                self.on_focus_change(None)

        self._update_empty_state()
        self._position_indicator()
        return True

    def focus_tab(self, tab_id: int) -> bool:
        """Set *tab_id* as the active tab and invoke ``on_focus_change``."""
        if tab_id not in self._tabs:
            return False
        self.active = tab_id
        self._update_styles()
        if self.on_focus_change:
            self.on_focus_change(tab_id)
        return True

    def has_tab(self, tab_id: int) -> bool:
        """Return whether a tab with *tab_id* is currently open."""
        return tab_id in self._tabs

    def get_tab_idx(self, tab_id: int) -> int:
        """Return the 0-based position of *tab_id*, or -1 if not present."""
        ids = list(self._tabs.keys())
        return ids.index(tab_id) if tab_id in ids else -1

    def get_tab_label(self, tab_id: int) -> str | None:
        """Return the current display label of *tab_id*, or None."""
        entry = self._tabs.get(tab_id)
        return entry.get("label") if entry else None

    def update_tab_label(self, tab_id: int, label: str):
        """Update the displayed text of *tab_id*'s button."""
        if tab_id in self._tabs:
            self._tabs[tab_id]["label"] = label
            self._tabs[tab_id]["button"].config(text=label)
            self._position_indicator()

    def set_focused_style(self, focused: bool):
        """Toggle the visual focused/unfocused state of the bar.

        When focused the bar uses the normal background; when unfocused
        it dims slightly so the user can see which pane is active.
        """
        if self._focused == focused:
            return
        self._focused = focused
        self.configure(bg=self._pal.focused if focused else self._pal.unfocused)
        for tab_id, entry in self._tabs.items():
            bg = self._tab_bg(tab_id)
            entry["button"].configure(bg=bg, fg=self._tab_fg(tab_id))
            entry["close"].configure(bg=bg, fg=self._tab_fg(tab_id))
        self._position_indicator()

    def set_insert_indicator(self, idx: int, drag_id: int | None = None):
        """Show the insertion indicator for a drop at position *idx*."""
        if not self._tabs:
            # Empty bar — expand highlight and show horizontal indicator at bottom
            self.configure(bg=self._pal.empty_hover)
            h = self.winfo_height() or _EMPTY_BAR_H
            w = self.winfo_width() or 200
            if self._insert_indicator is None:
                self._insert_indicator = Frame(self, height=3, bg=self._pal.accent)
            self._insert_indicator.place(x=0, y=h - 3, width=w, height=3)
            self._insert_indicator.lift()
        else:
            x = self._get_insert_x(idx, drag_id)
            h = self.winfo_height() or 24
            if self._insert_indicator is None:
                self._insert_indicator = Frame(self, width=3, bg=self._pal.accent)
            self._insert_indicator.place(x=max(0, x - 1), y=0, width=3, height=h)
            self._insert_indicator.lift()

    def clear_insert_indicator(self):
        """Hide the insertion indicator."""
        if self._insert_indicator is not None:
            self._insert_indicator.place_forget()
        if not self._tabs:
            # Return empty bar to its resting colour
            self.configure(bg=self._pal.empty)

    def destroy(self):
        """Deregister from the global registry before destroying."""
        try:
            _TABBAR_REGISTRY.remove(self)
        except ValueError:
            pass
        super().destroy()

    # ── Style: instance application ─────────────────────────────────────────────

    def apply_style(self, resolved) -> None:
        """Adopt *resolved* (a :class:`~VIStk.Styles.ResolvedStyle`) live.

        Recolours the strip and every live tab in place.  When the corner
        radius crosses 0 (plain button <-> rounded pill) the tab buttons are of
        a different widget class, so they are rebuilt; otherwise only colours,
        the separators, and the active indicator change — no navigation
        callbacks fire.
        """
        radius_changed = (self.style.radius > 0) != (resolved.radius > 0)
        self.style = resolved
        self.configure(bg=self._pal.focused if self._focused else self._pal.unfocused)
        if radius_changed:
            self._rebuild_all_tabs()
        else:
            self._restyle_tabs()
            self._rebuild_packing(list(self._tabs.keys()))
        self._update_empty_state()
        self._position_indicator()

    def _restyle_tabs(self) -> None:
        """Recolour every live tab widget to the current palette (no rebuild).

        Pill tabs are ``vButton``s that mirror ``activebackground`` from their own
        resting ``bg``, so only the plain-``Button`` style carries a native hover
        colour (see :meth:`_make_tab_button`)."""
        pill = self.style.radius > 0
        for tab_id, entry in self._tabs.items():
            bg = self._tab_bg(tab_id)
            entry["button"].configure(bg=bg, fg=self._tab_fg(tab_id))
            entry["close"].configure(bg=bg, fg=self._tab_fg(tab_id))
            if not pill:
                entry["button"].configure(activebackground=self._pal.tab_hover)
                entry["close"].configure(activebackground=self._pal.close_hover)

    def _rebuild_all_tabs(self) -> None:
        """Destroy and recreate every tab button under the current style.

        Used when the radius crosses 0 (Button <-> vButton).  Navigation
        callbacks are suppressed so re-adding tabs doesn't re-fire screen
        focus; the previously-active tab is restored silently.
        """
        order = list(self._tabs.keys())
        saved = {i: (self._tabs[i]["label"], self._tabs[i]["icon"]) for i in order}
        active = self.active

        for i in order:
            w = self._tabs[i]
            if w["sep"]:
                w["sep"].destroy()
            w["button"].destroy()
            w["close"].destroy()
        self._tabs = {}
        self.active = None

        cb = self.on_focus_change
        self.on_focus_change = None
        try:
            for i in order:
                lbl, icon = saved[i]
                self.open_tab(i, lbl, icon)
        finally:
            self.on_focus_change = cb

        if active is not None and active in self._tabs:
            self.active = active
        self._update_styles()

    # ── Widget factories (style-aware) ──────────────────────────────────────────

    def _make_separator(self):
        """Create a divider Frame, or ``None`` when the style omits separators."""
        if not self.style.separators:
            return None
        if self._is_vertical():
            sep = Frame(self, height=1, bg=self._pal.separator)
            sep.pack(side="top", fill="x", padx=3)
        else:
            sep = Frame(self, width=1, bg=self._pal.separator)
            sep.pack(side="left", fill="y", pady=3)
        return sep

    def _make_tab_button(self, tab_id: int, label: str, icon):
        """Build the tab's label button — a rounded ``vButton`` when the style
        has a radius, else a plain ``Button``."""
        pill = self.style.radius > 0
        common = dict(
            text=label,
            image=icon,
            compound="left" if icon else "none",
            relief="flat",
            bd=0,
            highlightthickness=0,
            takefocus=0,
            padx=_TAB_PADX,
            pady=_TAB_PADY,
            bg=self._pal.tab_inactive,
            fg=self._pal.tab_fg,
            command=lambda i=tab_id: self._btn_click(i),
        )
        if pill:
            # No active_fill: TabBar's own <Enter>/<Leave> handlers drive hover
            # uniformly for both button kinds (config(bg=...) repaints the tiles),
            # so vButton must not also bind its internal hover and fight them.
            # No activebackground either — Tk sets -state active from Tcl on
            # press, which never reaches Python to repaint, so a hover colour
            # there would paint the native square face over the pill (and a drag
            # that eats the release makes it permanent).  vButton mirrors the
            # resting bg onto activebackground for us instead.
            # A full-percent radius makes a capsule at any size; only the left
            # end is rounded so the label + close read as one pill.
            from VIStk.Widgets._vButton import vButton
            btn = vButton(self, radius=100, radius_style="percent",
                          corners=_PILL_LEFT, **common)
            # Fill-mode rounding zeroes internal padding (padx would runaway-grow
            # the image), so widen the button by a fixed pixel amount instead —
            # the centred text then gains _PILL_LABEL_PADX of space each side.
            self._widen_pill_label(btn)
            return btn
        return Button(self, activebackground=self._pal.tab_hover, **common)

    def _widen_pill_label(self, btn) -> None:
        """Widen a fill-mode pill label to its text width + a little side space.

        ``padx`` can't be used (it feeds back into the image-fill sizing), and a
        pixel ``width`` is only known once the text has measured, so set it once
        the button has its natural size."""
        def _apply():
            try:
                if not btn.winfo_exists():
                    return
                natural = btn.winfo_reqwidth()
                if natural <= 1:                       # not measured yet — retry
                    btn.after(16, _apply)
                    return
                btn.configure(width=natural + 2 * _PILL_LABEL_PADX)
            except TclError:
                pass
        btn.after_idle(_apply)

    def _make_close_button(self, tab_id: int):
        """Build the ✕ close button — a right-rounded ``vButton`` under the pill
        style (so it caps the capsule the label opens), else a plain ``Button``.

        The pill close carries a rounded fill *image*, so Tk would read a
        ``width`` as pixels (clipping the ✕ to a sliver); it sizes to content
        instead, while the plain Button keeps a 2-character width.
        """
        pill = self.style.radius > 0
        common = dict(
            text="✕",
            relief="flat",
            bd=0,
            highlightthickness=0,
            takefocus=0,
            padx=_PILL_CLOSE_PADX if pill else _CLOSE_PADX,
            font=_CLOSE_FONT,
            bg=self._pal.tab_inactive,
            fg=self._pal.tab_fg,
            command=lambda i=tab_id: self._close(i),
        )
        if pill:
            # activebackground is left off for the same reason as the label pill
            # — see _make_tab_button.
            from VIStk.Widgets._vButton import vButton
            return vButton(self, radius=100, radius_style="percent",
                           corners=_PILL_RIGHT, **common)
        return Button(self, width=2, activebackground=self._pal.close_hover,
                      **common)

    def _pack_tab(self, btn, close, *, first: bool) -> None:
        """Pack a tab's label + close under the active style's geometry.

        Non-pill tabs fill the full bar height and butt flush (dividers come
        from separators or the internal label padding).  Pill tabs are inset
        vertically so the capsule floats, and gapped on the left (from the bar
        edge and from the previous pill); the label and close stay flush to each
        other so their two rounded ends form one capsule.
        """
        if self._is_vertical():
            btn.pack(side="top", fill="x", padx=2, pady=(4, 0))
            close.pack(side="top", fill="x", padx=2, pady=(0, 4))
            return
        pill = self.style.radius > 0
        pady = _PILL_PADY if pill else 0
        lead = _PILL_GAP if pill else 0
        btn.pack(side="left", fill="y", pady=pady, padx=(lead, 0))
        close.pack(side="left", fill="y", pady=pady)

    # ── Active-tab indicator (underline / topline) ─────────────────────────────

    def _position_indicator(self):
        """Show/hide + reposition the accent bar under the active tab.

        A no-op for the ``none`` indicator (classic/pill), where the active
        tab is distinguished by its fill.  Deferred to ``after_idle`` so the
        button geometry is settled before it is measured.
        """
        if self._active_indicator is not None:
            self._active_indicator.place_forget()
        if self.style.indicator == "none" or self.active is None \
                or self.active not in self._tabs:
            return
        if self._active_indicator is None:
            self._active_indicator = Frame(self, bg=self._pal.accent)
        else:
            self._active_indicator.configure(bg=self._pal.accent)
        self.after_idle(self._place_indicator)

    def _place_indicator(self, _tries: int = 0):
        """Position the accent bar over the active tab.

        A freshly-packed tab (on launch or when a new tab is opened) has no
        real geometry yet when this first runs — ``winfo_*`` report ~0 and the
        bar would be placed with zero span, staying invisible until the user
        interacts.  When the measured span/bar size isn't ready we reschedule a
        few frames later instead of placing a degenerate bar.
        """
        try:
            if self._active_indicator is None or self.style.indicator == "none":
                return
            if self.active is None or self.active not in self._tabs:
                return
            btn = self._tabs[self.active]["button"]
            close = self._tabs[self.active]["close"]
            if self._is_vertical():
                y0 = btn.winfo_y()
                y1 = close.winfo_y() + close.winfo_height()
                span = y1 - y0
                bar_dim = self.winfo_width()
                if (span <= 1 or bar_dim <= 1) and _tries < 12:
                    self.after(16, lambda: self._place_indicator(_tries + 1))
                    return
                edge = 0 if (self._position == "left") ^ (self.style.indicator == "topline") \
                    else max(0, bar_dim - 3)
                self._active_indicator.place(x=edge, y=y0, width=3,
                                             height=max(0, span))
            else:
                x0 = btn.winfo_x()
                x1 = close.winfo_x() + close.winfo_width()
                span = x1 - x0
                h = self.winfo_height()
                if (span <= 1 or h <= 1) and _tries < 12:
                    self.after(16, lambda: self._place_indicator(_tries + 1))
                    return
                y = (h - 3) if self.style.indicator == "underline" else 0
                self._active_indicator.place(x=x0, y=y, width=max(0, span),
                                             height=3)
            self._active_indicator.lift()
        except TclError:
            pass

    def _on_configure(self, _event=None):
        """Re-place the active indicator when the bar is (re)sized or mapped.

        The initial ``_position_indicator`` on tab open schedules placement via
        ``after_idle``, which on launch fires before the bar has its real
        geometry — leaving an underline/topline marker invisible until the user
        first clicks a tab.  ``<Configure>`` fires once the bar is mapped and
        sized, so repositioning here makes the marker appear as soon as the
        layout settles.  A no-op for the ``none`` indicator (classic/pill).
        """
        if self.style.indicator != "none":
            self._position_indicator()

    # ── Empty-state management ─────────────────────────────────────────────────

    def _update_empty_state(self):
        if self._tabs:
            self.pack_propagate(True)
            self.configure(bg=self._pal.focused if self._focused else self._pal.unfocused)
            self.after_idle(self._capture_natural_size)
        else:
            self.pack_propagate(False)
            if self._is_vertical():
                w = self._natural_width or _EMPTY_BAR_W
                self.configure(width=w, bg=self._pal.empty)
            else:
                h = self._natural_height or _EMPTY_BAR_H
                self.configure(height=h, bg=self._pal.empty)

    def _capture_natural_size(self):
        """Remember the populated bar size so the empty state matches it."""
        try:
            if not self._tabs:
                return
            self.update_idletasks()
            if self._is_vertical():
                w = self.winfo_width()
                if w > 1:
                    self._natural_width = w
            else:
                h = self.winfo_height()
                if h > 1:
                    self._natural_height = h
        except TclError:
            pass

    # ── Right-click context menu ───────────────────────────────────────────────

    def _on_right_click(self, event, tab_id: int):
        menu = Menu(self, tearoff=0)
        menu.add_command(label="Open in new window",
                         command=lambda: self._do_popout(tab_id))
        menu.add_command(label="Split right",
                         command=lambda: self._do_split(tab_id, "right"))
        menu.add_command(label="Split down",
                         command=lambda: self._do_split(tab_id, "down"))
        menu.add_command(label="Force refresh",
                         command=lambda: self._do_refresh(tab_id))
        menu.add_separator()
        menu.add_command(label="Close",
                         command=lambda: self._close(tab_id))
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _do_popout(self, tab_id: int):
        if self.on_tab_popout:
            self.on_tab_popout(tab_id)

    def _do_split(self, tab_id: int, direction: str):
        if self.on_tab_split:
            self.on_tab_split(tab_id, direction)

    def _do_refresh(self, tab_id: int):
        if self.on_tab_refresh:
            self.on_tab_refresh(tab_id)

    # ── Ghost window helpers ───────────────────────────────────────────────────

    def _create_ghost(self, tab_id: int, x: int, y: int):
        """Create the semi-transparent drag ghost positioned at cursor."""
        if self._ghost is not None:
            return
        entry = self._tabs.get(tab_id, {})
        icon = entry.get("icon")
        label = entry.get("label", "")
        ghost = Toplevel()
        ghost.overrideredirect(True)
        ghost.attributes("-alpha", 0.75)
        ghost.attributes("-topmost", True)
        ghost.configure(bg=self._pal.tab_active)
        lbl = Label(
            ghost,
            text=label,
            image=icon,
            compound="left" if icon else "none",
            bg=self._pal.tab_active,
            fg=self._pal.tab_active_fg,
            padx=6,
            pady=3,
        )
        lbl.pack()
        ghost.update_idletasks()
        # Place ghost so cursor is at the same offset it had in the original tab
        ghost.geometry(f"+{x - self._drag_btn_offset_x}+{y - self._drag_btn_offset_y}")
        self._ghost = ghost
        # Dim the dragged tab while ghost is live
        if tab_id in self._tabs:
            self._tabs[tab_id]["button"].config(bg=self._pal.tab_drag)
            self._tabs[tab_id]["close"].config(bg=self._pal.tab_drag)

    def _update_ghost(self, x: int, y: int):
        if self._ghost is None:
            return
        try:
            self._ghost.geometry(
                f"+{x - self._drag_btn_offset_x}+{y - self._drag_btn_offset_y}"
            )
        except TclError:
            pass

    def _destroy_ghost(self, tab_id: int | None = None):
        if self._ghost is not None:
            try:
                self._ghost.destroy()
            except TclError:
                pass
            self._ghost = None
        n = tab_id if tab_id is not None else self._drag_id
        if n is not None and n in self._tabs:
            bg = self._tab_bg(n)
            self._tabs[n]["button"].config(bg=bg)
            self._tabs[n]["close"].config(bg=bg)

    # ── Insertion indicator helpers ────────────────────────────────────────────

    def _get_insert_idx_at(self, x_root: int, drag_id: int | None = None) -> int:
        """Return the insertion index for a drop at screen x *x_root*."""
        ids = [i for i in self._tabs.keys() if i != drag_id]
        for i, tid in enumerate(ids):
            try:
                bx = self._tabs[tid]["button"].winfo_rootx()
                bw = self._tabs[tid]["button"].winfo_width()
            except TclError:
                continue
            if x_root < bx + bw // 2:
                return i
        return len(ids)

    def _get_insert_x(self, idx: int, drag_id: int | None = None) -> int:
        """Return the bar-relative x where the vertical indicator should appear."""
        ids = [i for i in self._tabs.keys() if i != drag_id]
        if not ids:
            return 0
        if idx <= 0:
            try:
                return self._tabs[ids[0]]["button"].winfo_x()
            except TclError:
                return 0
        if idx >= len(ids):
            try:
                c = self._tabs[ids[-1]]["close"]
                return c.winfo_x() + c.winfo_width() + 2
            except TclError:
                return max(0, self.winfo_width() - 4)
        try:
            prev_c = self._tabs[ids[idx - 1]]["close"]
            cur_b  = self._tabs[ids[idx]]["button"]
            px = prev_c.winfo_x() + prev_c.winfo_width()
            cx = cur_b.winfo_x()
            return (px + cx) // 2
        except TclError:
            return 0

    # ── Drag-to-reorder / detach / merge ──────────────────────────────────────

    def _on_drag_start(self, event, tab_id: int):
        self._drag_id     = tab_id
        self._drag_start_x = event.x_root
        self._drag_start_y = event.y_root
        self._drag_active  = False
        # Cursor offset within the tab button — persisted so Host can read after drag ends
        try:
            btn = self._tabs[tab_id]["button"]
            self._drag_btn_offset_x = event.x_root - btn.winfo_rootx()
            self._drag_btn_offset_y = event.y_root - btn.winfo_rooty()
        except TclError:
            self._drag_btn_offset_x = 0
            self._drag_btn_offset_y = 0
        self._last_drag_btn_offset_x = self._drag_btn_offset_x
        self._last_drag_btn_offset_y = self._drag_btn_offset_y
        # Clear stale indicator state
        if self._insert_bar:
            self._insert_bar.clear_insert_indicator()
        self._insert_bar = None
        self._insert_idx = -1

    def _on_drag_motion(self, event, tab_id: int):
        if self._drag_id is None:
            return

        dx = abs(event.x_root - self._drag_start_x)
        dy = abs(event.y_root - self._drag_start_y)
        if dx >= _DRAG_THRESHOLD or dy >= _DRAG_THRESHOLD:
            self._drag_active = True

        if not self._drag_active:
            return

        # Create ghost on first motion past threshold
        if self._ghost is None:
            self._create_ghost(tab_id, event.x_root, event.y_root)
        else:
            self._update_ghost(event.x_root, event.y_root)

        # Find which registered bar the cursor is over
        x, y = event.x_root, event.y_root
        target_bar: "TabBar | None" = None
        for bar in _TABBAR_REGISTRY:
            try:
                bx = bar.winfo_rootx()
                by = bar.winfo_rooty()
                bw = bar.winfo_width()
                bh = bar.winfo_height()
            except TclError:
                continue
            if bx <= x < bx + bw and by <= y < by + bh:
                target_bar = bar
                break

        if target_bar is not None:
            drag = self._drag_id if target_bar is self else None
            idx  = target_bar._get_insert_idx_at(x, drag)
            if self._insert_bar is not None and self._insert_bar is not target_bar:
                self._insert_bar.clear_insert_indicator()
            self._insert_bar = target_bar
            self._insert_idx = idx
            target_bar.set_insert_indicator(idx, drag)
            # Clear any drop-zone overlay when over a tab bar
            if self.on_drag_zone:
                self.on_drag_zone("hide", x, y)
        else:
            if self._insert_bar is not None:
                self._insert_bar.clear_insert_indicator()
            self._insert_bar = None
            self._insert_idx = -1
            # Check for split drop zones in pane content areas
            if self.on_drag_zone:
                self.on_drag_zone("check", x, y)

    def _on_drag_release(self, event):
        drag_id    = self._drag_id
        insert_bar = self._insert_bar
        insert_idx = self._insert_idx

        self._drag_id    = None
        self._insert_bar = None
        self._insert_idx = -1

        if insert_bar is not None:
            insert_bar.clear_insert_indicator()

        if not self._drag_active or drag_id is None:
            self._destroy_ghost(drag_id)
            if self.on_drag_zone:
                self.on_drag_zone("hide", 0, 0)
            return

        if insert_bar is self:
            self._destroy_ghost(drag_id)
            self._reorder_to_idx(drag_id, insert_idx)
        elif insert_bar is not None:
            self._destroy_ghost(drag_id)
            if insert_bar.on_drag_merge:
                insert_bar.on_drag_merge(drag_id, self, insert_idx)
        else:
            # Check if dropping on a split zone
            drop_info = None
            if self.on_drag_zone:
                drop_info = self.on_drag_zone("drop", event.x_root, event.y_root)
            if drop_info is not None:
                self._destroy_ghost(drag_id)
                pane, direction = drop_info
                if self.on_tab_split:
                    self.on_tab_split(drag_id, direction, pane)
            else:
                # Transfer ghost ownership — keep alive while DetachedWindow is created
                # and positioned, so the user sees no gap between ghost and window.
                ghost = self._ghost
                self._ghost = None
                if self.on_drag_detach:
                    self.on_drag_detach(drag_id)
                if ghost is not None:
                    try:
                        ghost.destroy()
                    except TclError:
                        pass
        # For same-bar reorder, _btn_click fires from the ButtonRelease and clears
        # _drag_active.  For merge/detach/split the release is on a different widget,
        # so _btn_click never fires — clear the flag here to prevent the next click
        # from being silently suppressed.
        if insert_bar is not self:
            self._drag_active = False

    def _reorder_to_idx(self, dragged: int, idx: int):
        """Move *dragged* to 0-based position *idx* (in the without-dragged space)."""
        ids = list(self._tabs.keys())
        if dragged not in ids:
            return
        ids.remove(dragged)
        idx = max(0, min(idx, len(ids)))
        ids.insert(idx, dragged)
        self._rebuild_packing(ids)

    def _rebuild_packing(self, new_order: list[int]):
        """Repack all tab widgets in *new_order*, rebuilding separators.

        Also reconciles separators with the active style: a style with
        ``separators=False`` drops any existing dividers, and one with them on
        recreates the missing ones.
        """
        for w in self._tabs.values():
            if w["sep"]:
                w["sep"].pack_forget()
            w["button"].pack_forget()
            w["close"].pack_forget()

        new_tabs: dict[int, dict] = {}
        for i, tab_id in enumerate(new_order):
            w = self._tabs[tab_id]
            need_sep = self.style.separators and i > 0
            if not need_sep:
                if w["sep"]:
                    w["sep"].destroy()
                    w["sep"] = None
            else:
                if not w["sep"]:
                    if self._is_vertical():
                        w["sep"] = Frame(self, height=1, bg=self._pal.separator)
                    else:
                        w["sep"] = Frame(self, width=1, bg=self._pal.separator)
                else:
                    w["sep"].configure(bg=self._pal.separator)
                if self._is_vertical():
                    w["sep"].pack(side="top", fill="x", padx=3)
                else:
                    w["sep"].pack(side="left", fill="y", pady=3)
            self._pack_tab(w["button"], w["close"], first=(i == 0))
            new_tabs[tab_id] = w
        self._tabs = new_tabs
        self._position_indicator()

    # ── Internal ───────────────────────────────────────────────────────────────

    def _btn_click(self, tab_id: int):
        """Focus the tab only when the press was a genuine click (not a drag)."""
        was_drag = self._drag_active
        self._drag_active = False
        if not was_drag:
            self.focus_tab(tab_id)

    def _tab_bg(self, tab_id: int) -> str:
        if tab_id == self.active:
            return self._pal.tab_active if self._focused else self._pal.active_unfocused
        return self._pal.tab_inactive if self._focused else self._pal.unfocused

    def _tab_fg(self, tab_id: int) -> str:
        if tab_id == self.active:
            return self._pal.tab_active_fg
        return self._pal.tab_fg

    def _close(self, tab_id: int):
        if self.on_tab_close:
            self.on_tab_close(tab_id)
        else:
            self.close_tab(tab_id)

    def _on_tab_enter(self, tab_id: int):
        if tab_id not in self._tabs:
            return
        # Always highlight inactive tabs; highlight active tab only in unfocused panes
        if tab_id != self.active or not self._focused:
            self._tabs[tab_id]["button"].config(bg=self._pal.tab_hover)
            self._tabs[tab_id]["close"].config(bg=self._pal.tab_hover)

    def _on_tab_leave(self, tab_id: int):
        if tab_id in self._tabs:
            bg = self._tab_bg(tab_id)
            self._tabs[tab_id]["button"].config(bg=bg)
            self._tabs[tab_id]["close"].config(bg=bg)

    def _on_close_enter(self, tab_id: int):
        if tab_id in self._tabs:
            self._tabs[tab_id]["close"].config(bg=self._pal.close_hover)

    def _on_close_leave(self, tab_id: int):
        if tab_id in self._tabs:
            self._tabs[tab_id]["close"].config(bg=self._tab_bg(tab_id))

    def _update_styles(self):
        for tab_id, widgets in self._tabs.items():
            bg = self._tab_bg(tab_id)
            widgets["button"].config(relief="flat", bg=bg, fg=self._tab_fg(tab_id))
            widgets["close"].config(relief="flat", bg=bg, fg=self._tab_fg(tab_id))
        self._position_indicator()
