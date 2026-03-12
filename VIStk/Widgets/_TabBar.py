from tkinter import Frame, Button

# ── Palette ───────────────────────────────────────────────────────────────────
_BG_BAR          = "grey62"    # tab strip background
_BG_ACTIVE       = "grey85"    # selected tab + its close button
_BG_INACTIVE     = "grey62"    # unselected tab (matches strip)
_BG_HOVER_TAB    = "grey72"    # hover over an unselected tab
_BG_HOVER_CLOSE  = "IndianRed" # hover over any close button
_SEP_BG          = "grey50"    # vertical divider between tabs

_DRAG_THRESHOLD  = 8           # pixels of horizontal motion to start a drag


class TabBar(Frame):
    """A row of clickable tabs displayed at the top of the Host window.

    Each tab represents an open screen.  Clicking a tab focuses it; the close
    button (✕) closes it; and tabs can be dragged left or right to reorder them.
    A thin vertical separator is drawn between adjacent tabs.

    Attributes:
        active (str | None): Name of the currently focused tab.
        on_focus_change (callable | None): Invoked with ``(name: str | None)``
            whenever the active tab changes (``None`` when all tabs close).
        on_tab_close (callable | None): Invoked with ``(name: str)`` when a
            tab's close button is pressed, *before* the tab is removed.
    """

    def __init__(self, parent, **kwargs):
        kwargs.setdefault("bg", _BG_BAR)
        super().__init__(parent, **kwargs)
        self._tabs: dict[str, dict] = {}
        """name → {"button": Button, "close": Button, "sep": Frame|None, "icon": image|None}"""
        self.active: str | None = None
        self.on_focus_change = None
        self.on_tab_close    = None

        # Drag-to-reorder state
        self._drag_name: str | None = None
        self._drag_start_x: int = 0
        self._drag_active: bool = False

    # ── Public API ─────────────────────────────────────────────────────────────

    def open_tab(self, name: str, icon=None) -> bool:
        """Add a tab for *name*.  Does nothing if the tab already exists.

        Args:
            name: Label shown on the tab button.
            icon: Optional ``PIL.ImageTk.PhotoImage`` shown to the left of the
                  label.  The reference must already be kept alive by the caller.

        Returns:
            True if a new tab was created, False if it already existed.
        """
        if name in self._tabs:
            return False

        # Separator before every tab except the first
        sep = None
        if self._tabs:
            sep = Frame(self, width=1, bg=_SEP_BG)
            sep.pack(side="left", fill="y", pady=3)

        btn = Button(
            self,
            text=name,
            image=icon,
            compound="left" if icon else "none",
            relief="flat",
            bd=0,
            bg=_BG_INACTIVE,
            activebackground=_BG_HOVER_TAB,
            command=lambda n=name: self._btn_click(n),
        )
        btn.pack(side="left", padx=(4, 0), pady=2)

        # Drag bindings on the tab label button
        btn.bind("<ButtonPress-1>",   lambda e, n=name: self._on_drag_start(e, n))
        btn.bind("<B1-Motion>",       lambda e, n=name: self._on_drag_motion(e, n))
        btn.bind("<ButtonRelease-1>", lambda e: self._on_drag_release(e))

        close_btn = Button(
            self,
            text="✕",
            relief="flat",
            bd=0,
            width=2,
            bg=_BG_INACTIVE,
            activebackground=_BG_HOVER_CLOSE,
            command=lambda n=name: self._close(n),
        )
        close_btn.pack(side="left", padx=(0, 4), pady=2)

        # Hover bindings
        btn.bind("<Enter>",       lambda e, n=name: self._on_tab_enter(n))
        btn.bind("<Leave>",       lambda e, n=name: self._on_tab_leave(n))
        close_btn.bind("<Enter>", lambda e, n=name: self._on_close_enter(n))
        close_btn.bind("<Leave>", lambda e, n=name: self._on_close_leave(n))

        self._tabs[name] = {"button": btn, "close": close_btn, "sep": sep, "icon": icon}
        self.focus_tab(name)
        return True

    def close_tab(self, name: str) -> bool:
        """Remove the tab for *name*.

        Handles separator ownership: if the first tab is closed the new first
        tab's separator (which would now be orphaned on the left) is also
        removed.

        Returns:
            True if removed, False if not found.
        """
        if name not in self._tabs:
            return False

        tab_names = list(self._tabs.keys())
        tab_idx   = tab_names.index(name)

        if self._tabs[name]["sep"]:
            self._tabs[name]["sep"].destroy()
        self._tabs[name]["button"].destroy()
        self._tabs[name]["close"].destroy()
        del self._tabs[name]

        # If first tab was removed, strip the orphaned separator from the new first
        if tab_idx == 0 and self._tabs:
            new_first = list(self._tabs.keys())[0]
            if self._tabs[new_first]["sep"]:
                self._tabs[new_first]["sep"].destroy()
                self._tabs[new_first]["sep"] = None

        if self.active == name:
            self.active = None
            remaining = list(self._tabs.keys())
            if remaining:
                self.focus_tab(remaining[-1])
            elif self.on_focus_change:
                self.on_focus_change(None)
        return True

    def focus_tab(self, name: str) -> bool:
        """Set *name* as the active tab and invoke ``on_focus_change``.

        Returns:
            True if focus was set, False if tab not found.
        """
        if name not in self._tabs:
            return False
        self.active = name
        self._update_styles()
        if self.on_focus_change:
            self.on_focus_change(name)
        return True

    def has_tab(self, name: str) -> bool:
        """Return whether a tab with *name* is currently open."""
        return name in self._tabs

    # ── Drag-to-reorder ────────────────────────────────────────────────────────

    def _on_drag_start(self, event, name: str):
        self._drag_name = name
        self._drag_start_x = event.x_root
        self._drag_active = False

    def _on_drag_motion(self, event, name: str):
        if not self._drag_name:
            return
        if abs(event.x_root - self._drag_start_x) >= _DRAG_THRESHOLD:
            self._drag_active = True

        if not self._drag_active:
            return

        x = event.x_root
        for tname, w in self._tabs.items():
            if tname == self._drag_name:
                continue
            btn = w["button"]
            bx = btn.winfo_rootx()
            bw = btn.winfo_width()
            if bx <= x < bx + bw:
                insert_after = x > bx + bw // 2
                self._reorder(self._drag_name, tname, insert_after)
                break

    def _on_drag_release(self, event):
        self._drag_name = None
        self._drag_active = False

    def _reorder(self, dragged: str, target: str, insert_after: bool):
        """Move *dragged* tab to immediately before/after *target* and repack."""
        names = list(self._tabs.keys())
        if dragged not in names or target not in names:
            return
        names.remove(dragged)
        idx = names.index(target)
        names.insert(idx + 1 if insert_after else idx, dragged)
        self._rebuild_packing(names)

    def _rebuild_packing(self, new_order: list[str]):
        """Repack all tab widgets in *new_order*, rebuilding separators."""
        # Unpack everything
        for w in self._tabs.values():
            if w["sep"]:
                w["sep"].pack_forget()
            w["button"].pack_forget()
            w["close"].pack_forget()

        new_tabs: dict[str, dict] = {}
        for i, name in enumerate(new_order):
            w = self._tabs[name]

            # First tab has no separator; all others need one
            if i == 0:
                if w["sep"]:
                    w["sep"].destroy()
                    w["sep"] = None
            else:
                if not w["sep"]:
                    w["sep"] = Frame(self, width=1, bg=_SEP_BG)
                w["sep"].pack(side="left", fill="y", pady=3)

            w["button"].pack(side="left", padx=(4, 0), pady=2)
            w["close"].pack(side="left", padx=(0, 4), pady=2)
            new_tabs[name] = w

        self._tabs = new_tabs

    # ── Internal ───────────────────────────────────────────────────────────────

    def _btn_click(self, name: str):
        """Focus the tab only when the press was a genuine click (not a drag)."""
        if not self._drag_active:
            self.focus_tab(name)

    def _tab_bg(self, name: str) -> str:
        return _BG_ACTIVE if name == self.active else _BG_INACTIVE

    def _close(self, name: str):
        if self.on_tab_close:
            self.on_tab_close(name)
        self.close_tab(name)

    def _on_tab_enter(self, name: str):
        if name in self._tabs and name != self.active:
            self._tabs[name]["button"].config(bg=_BG_HOVER_TAB)
            self._tabs[name]["close"].config(bg=_BG_HOVER_TAB)

    def _on_tab_leave(self, name: str):
        if name in self._tabs:
            bg = self._tab_bg(name)
            self._tabs[name]["button"].config(bg=bg)
            self._tabs[name]["close"].config(bg=bg)

    def _on_close_enter(self, name: str):
        if name in self._tabs:
            self._tabs[name]["close"].config(bg=_BG_HOVER_CLOSE)

    def _on_close_leave(self, name: str):
        if name in self._tabs:
            self._tabs[name]["close"].config(bg=self._tab_bg(name))

    def _update_styles(self):
        """Repaint all tabs to reflect the current ``active`` state."""
        for name, widgets in self._tabs.items():
            bg = self._tab_bg(name)
            widgets["button"].config(relief="flat", bg=bg)
            widgets["close"].config(relief="flat", bg=bg)
