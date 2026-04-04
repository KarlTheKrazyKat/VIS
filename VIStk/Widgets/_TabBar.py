from tkinter import Frame, Button, Label, Menu, Toplevel

# ── Palette ───────────────────────────────────────────────────────────────────
_BG_BAR          = "grey62"    # tab strip background
_BG_ACTIVE       = "grey85"    # selected tab + its close button
_BG_INACTIVE     = "grey62"    # unselected tab (matches strip)
_BG_HOVER_TAB    = "grey72"    # hover over an unselected tab
_BG_HOVER_CLOSE  = "IndianRed" # hover over any close button
_SEP_BG          = "grey50"    # vertical divider between tabs
_INDICATOR_COLOR = "dodger blue"  # drag insertion indicator
_BG_EMPTY        = "grey55"    # empty bar thin drop-zone line
_BG_HOVER_EMPTY  = "grey68"    # empty bar highlighted during drag hover

_DRAG_THRESHOLD  = 8           # pixels of motion (any direction) to activate drag ghost
_EMPTY_BAR_H     = 28          # height of the bar when no tabs are open

# ── Global registry ───────────────────────────────────────────────────────────
# All live TabBar instances register here so cross-bar detection works.
_TABBAR_REGISTRY: list["TabBar"] = []


class TabBar(Frame):
    """A row of clickable tabs displayed at the top of a ``TabManager``.

    During a drag a semi-transparent ghost Toplevel follows the cursor.  Tabs
    do not slide until the mouse is released.  A coloured insertion indicator
    appears in the hovered bar.  On release: reorder in the same bar / merge
    into another bar / detach if the cursor is outside all bars.

    When no tabs are open the bar shrinks to a visible drop-zone strip.
    Drags hovering over an empty bar expand and highlight it.

    Right-click: "Open in new window", "Force refresh", "Close".

    Attributes:
        active            (str | None)
        owner             (TabManager | None)  set by TabManager after init
        on_focus_change   (callable | None)   ``(name: str | None)``
        on_tab_close      (callable | None)   ``(name: str)``
        on_tab_popout     (callable | None)   ``(name: str)``
        on_tab_refresh    (callable | None)   ``(name: str)``
        on_drag_detach    (callable | None)   ``(name: str)``
        on_drag_merge     (callable | None)   ``(name: str, source: TabBar, idx: int)``

    After every drag ends ``_last_drag_btn_offset_x`` / ``_last_drag_btn_offset_y``
    hold the cursor's pixel offset within the dragged tab button.  External
    code (e.g. Host) may read these to position a new DetachedWindow.
    """

    def __init__(self, parent, **kwargs):
        kwargs.setdefault("bg", _BG_BAR)
        super().__init__(parent, **kwargs)
        self._tabs: dict[str, dict] = {}
        """name → {"button": Button, "close": Button, "sep": Frame|None, "icon": image|None}"""
        self.active: str | None = None
        self.owner = None               # set by TabManager

        # Callbacks
        self.on_focus_change = None
        self.on_tab_close    = None
        self.on_tab_popout   = None
        self.on_tab_refresh  = None
        self.on_drag_detach  = None
        self.on_drag_merge   = None     # (name, source_bar, insert_idx)
        self.on_tab_split    = None     # (name, direction)  "right" or "down"

        # Drag state
        self._drag_name: str | None = None
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

        # Cross-bar tracking (owned by the dragging bar)
        self._insert_bar: "TabBar | None" = None
        self._insert_idx: int = -1

        _TABBAR_REGISTRY.append(self)
        self._update_empty_state()

    # ── Public API ─────────────────────────────────────────────────────────────

    def open_tab(self, name: str, icon=None, insert_idx: int = -1) -> bool:
        """Add a tab for *name*.  Does nothing if it already exists.

        Args:
            name:       Label shown on the tab button.
            icon:       Optional ``PIL.ImageTk.PhotoImage`` shown left of label.
            insert_idx: 0-based position to insert at; -1 appends.

        Returns:
            ``True`` if a new tab was created, ``False`` if already existed.
        """
        if name in self._tabs:
            return False

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

        btn.bind("<ButtonPress-1>",   lambda e, n=name: self._on_drag_start(e, n))
        btn.bind("<B1-Motion>",       lambda e, n=name: self._on_drag_motion(e, n))
        btn.bind("<ButtonRelease-1>", lambda e: self._on_drag_release(e))
        btn.bind("<Button-3>",        lambda e, n=name: self._on_right_click(e, n))

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

        btn.bind("<Enter>",       lambda e, n=name: self._on_tab_enter(n))
        btn.bind("<Leave>",       lambda e, n=name: self._on_tab_leave(n))
        close_btn.bind("<Enter>", lambda e, n=name: self._on_close_enter(n))
        close_btn.bind("<Leave>", lambda e, n=name: self._on_close_leave(n))

        self._tabs[name] = {"button": btn, "close": close_btn, "sep": sep, "icon": icon}
        self.focus_tab(name)

        if insert_idx >= 0:
            names = list(self._tabs.keys())
            if name in names and len(names) > 1:
                self._reorder_to_idx(name, insert_idx)

        self._update_empty_state()
        return True

    def close_tab(self, name: str) -> bool:
        """Remove the tab for *name*.

        If the first tab is closed, the new first tab's orphaned separator is
        also removed.

        Returns:
            ``True`` if removed, ``False`` if not found.
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

        self._update_empty_state()
        return True

    def focus_tab(self, name: str) -> bool:
        """Set *name* as the active tab and invoke ``on_focus_change``."""
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

    def get_tab_idx(self, name: str) -> int:
        """Return the 0-based position of *name*, or -1 if not present."""
        names = list(self._tabs.keys())
        return names.index(name) if name in names else -1

    def update_tab_label(self, name: str, display: str):
        """Update the displayed text of tab *name*'s button."""
        if name in self._tabs:
            self._tabs[name]["button"].config(text=display)

    def set_insert_indicator(self, idx: int, drag_name: str = None):
        """Show the insertion indicator for a drop at position *idx*."""
        if not self._tabs:
            # Empty bar — expand highlight and show horizontal indicator at bottom
            self.configure(bg=_BG_HOVER_EMPTY)
            h = self.winfo_height() or _EMPTY_BAR_H
            w = self.winfo_width() or 200
            if self._insert_indicator is None:
                self._insert_indicator = Frame(self, height=3, bg=_INDICATOR_COLOR)
            self._insert_indicator.place(x=0, y=h - 3, width=w, height=3)
            self._insert_indicator.lift()
        else:
            x = self._get_insert_x(idx, drag_name)
            h = self.winfo_height() or 24
            if self._insert_indicator is None:
                self._insert_indicator = Frame(self, width=3, bg=_INDICATOR_COLOR)
            self._insert_indicator.place(x=max(0, x - 1), y=0, width=3, height=h)
            self._insert_indicator.lift()

    def clear_insert_indicator(self):
        """Hide the insertion indicator."""
        if self._insert_indicator is not None:
            self._insert_indicator.place_forget()
        if not self._tabs:
            # Return empty bar to its resting colour
            self.configure(bg=_BG_EMPTY)

    def destroy(self):
        """Deregister from the global registry before destroying."""
        try:
            _TABBAR_REGISTRY.remove(self)
        except ValueError:
            pass
        super().destroy()

    # ── Empty-state management ─────────────────────────────────────────────────

    def _update_empty_state(self):
        if self._tabs:
            self.pack_propagate(True)
            self.configure(bg=_BG_BAR)
        else:
            self.pack_propagate(False)
            self.configure(height=_EMPTY_BAR_H, bg=_BG_EMPTY)

    # ── Right-click context menu ───────────────────────────────────────────────

    def _on_right_click(self, event, name: str):
        menu = Menu(self, tearoff=0)
        menu.add_command(label="Open in new window",
                         command=lambda: self._do_popout(name))
        menu.add_command(label="Split right",
                         command=lambda: self._do_split(name, "right"))
        menu.add_command(label="Split down",
                         command=lambda: self._do_split(name, "down"))
        menu.add_command(label="Force refresh",
                         command=lambda: self._do_refresh(name))
        menu.add_separator()
        menu.add_command(label="Close",
                         command=lambda: self._close(name))
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _do_popout(self, name: str):
        if self.on_tab_popout:
            self.on_tab_popout(name)

    def _do_split(self, name: str, direction: str):
        if self.on_tab_split:
            self.on_tab_split(name, direction)

    def _do_refresh(self, name: str):
        if self.on_tab_refresh:
            self.on_tab_refresh(name)

    # ── Ghost window helpers ───────────────────────────────────────────────────

    def _create_ghost(self, name: str, x: int, y: int):
        """Create the semi-transparent drag ghost positioned at cursor."""
        if self._ghost is not None:
            return
        icon = self._tabs[name].get("icon")
        ghost = Toplevel()
        ghost.overrideredirect(True)
        ghost.attributes("-alpha", 0.75)
        ghost.attributes("-topmost", True)
        ghost.configure(bg=_BG_ACTIVE)
        lbl = Label(
            ghost,
            text=name,
            image=icon,
            compound="left" if icon else "none",
            bg=_BG_ACTIVE,
            fg="black",
            padx=6,
            pady=3,
        )
        lbl.pack()
        ghost.update_idletasks()
        # Place ghost so cursor is at the same offset it had in the original tab
        ghost.geometry(f"+{x - self._drag_btn_offset_x}+{y - self._drag_btn_offset_y}")
        self._ghost = ghost
        # Dim the dragged tab while ghost is live
        if name in self._tabs:
            self._tabs[name]["button"].config(bg="grey45")
            self._tabs[name]["close"].config(bg="grey45")

    def _update_ghost(self, x: int, y: int):
        if self._ghost is None:
            return
        try:
            self._ghost.geometry(
                f"+{x - self._drag_btn_offset_x}+{y - self._drag_btn_offset_y}"
            )
        except Exception:
            pass

    def _destroy_ghost(self, name: str | None = None):
        if self._ghost is not None:
            try:
                self._ghost.destroy()
            except Exception:
                pass
            self._ghost = None
        n = name or self._drag_name
        if n and n in self._tabs:
            bg = self._tab_bg(n)
            self._tabs[n]["button"].config(bg=bg)
            self._tabs[n]["close"].config(bg=bg)

    # ── Insertion indicator helpers ────────────────────────────────────────────

    def _get_insert_idx_at(self, x_root: int, drag_name: str = None) -> int:
        """Return the insertion index for a drop at screen x *x_root*."""
        names = [n for n in self._tabs.keys() if n != drag_name]
        for i, name in enumerate(names):
            try:
                bx = self._tabs[name]["button"].winfo_rootx()
                bw = self._tabs[name]["button"].winfo_width()
            except Exception:
                continue
            if x_root < bx + bw // 2:
                return i
        return len(names)

    def _get_insert_x(self, idx: int, drag_name: str = None) -> int:
        """Return the bar-relative x where the vertical indicator should appear."""
        names = [n for n in self._tabs.keys() if n != drag_name]
        if not names:
            return 0
        if idx <= 0:
            try:
                return self._tabs[names[0]]["button"].winfo_x()
            except Exception:
                return 0
        if idx >= len(names):
            try:
                c = self._tabs[names[-1]]["close"]
                return c.winfo_x() + c.winfo_width() + 2
            except Exception:
                return max(0, self.winfo_width() - 4)
        try:
            prev_c = self._tabs[names[idx - 1]]["close"]
            cur_b  = self._tabs[names[idx]]["button"]
            px = prev_c.winfo_x() + prev_c.winfo_width()
            cx = cur_b.winfo_x()
            return (px + cx) // 2
        except Exception:
            return 0

    # ── Drag-to-reorder / detach / merge ──────────────────────────────────────

    def _on_drag_start(self, event, name: str):
        self._drag_name    = name
        self._drag_start_x = event.x_root
        self._drag_start_y = event.y_root
        self._drag_active  = False
        # Cursor offset within the tab button — persisted so Host can read after drag ends
        try:
            btn = self._tabs[name]["button"]
            self._drag_btn_offset_x = event.x_root - btn.winfo_rootx()
            self._drag_btn_offset_y = event.y_root - btn.winfo_rooty()
        except Exception:
            self._drag_btn_offset_x = 0
            self._drag_btn_offset_y = 0
        self._last_drag_btn_offset_x = self._drag_btn_offset_x
        self._last_drag_btn_offset_y = self._drag_btn_offset_y
        # Clear stale indicator state
        if self._insert_bar:
            self._insert_bar.clear_insert_indicator()
        self._insert_bar = None
        self._insert_idx = -1

    def _on_drag_motion(self, event, name: str):
        if not self._drag_name:
            return

        dx = abs(event.x_root - self._drag_start_x)
        dy = abs(event.y_root - self._drag_start_y)
        if dx >= _DRAG_THRESHOLD or dy >= _DRAG_THRESHOLD:
            self._drag_active = True

        if not self._drag_active:
            return

        # Create ghost on first motion past threshold
        if self._ghost is None:
            self._create_ghost(name, event.x_root, event.y_root)
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
            except Exception:
                continue
            if bx <= x < bx + bw and by <= y < by + bh:
                target_bar = bar
                break

        if target_bar is not None:
            drag = self._drag_name if target_bar is self else None
            idx  = target_bar._get_insert_idx_at(x, drag)
            if self._insert_bar is not None and self._insert_bar is not target_bar:
                self._insert_bar.clear_insert_indicator()
            self._insert_bar = target_bar
            self._insert_idx = idx
            target_bar.set_insert_indicator(idx, drag)
        else:
            if self._insert_bar is not None:
                self._insert_bar.clear_insert_indicator()
            self._insert_bar = None
            self._insert_idx = -1

    def _on_drag_release(self, event):
        drag_name  = self._drag_name
        insert_bar = self._insert_bar
        insert_idx = self._insert_idx

        self._drag_name  = None
        self._insert_bar = None
        self._insert_idx = -1

        if insert_bar is not None:
            insert_bar.clear_insert_indicator()

        if not self._drag_active or drag_name is None:
            self._destroy_ghost(drag_name)
            return

        if insert_bar is self:
            self._destroy_ghost(drag_name)
            self._reorder_to_idx(drag_name, insert_idx)
        elif insert_bar is not None:
            self._destroy_ghost(drag_name)
            if insert_bar.on_drag_merge:
                insert_bar.on_drag_merge(drag_name, self, insert_idx)
        else:
            # Transfer ghost ownership — keep alive while DetachedWindow is created
            # and positioned, so the user sees no gap between ghost and window.
            ghost = self._ghost
            self._ghost = None
            if self.on_drag_detach:
                self.on_drag_detach(drag_name)
            if ghost is not None:
                try:
                    ghost.destroy()
                except Exception:
                    pass
        # _drag_active intentionally NOT cleared here; _btn_click reads and clears it

    def _reorder_to_idx(self, dragged: str, idx: int):
        """Move *dragged* to 0-based position *idx* (in the without-dragged space)."""
        names = list(self._tabs.keys())
        if dragged not in names:
            return
        names.remove(dragged)
        idx = max(0, min(idx, len(names)))
        names.insert(idx, dragged)
        self._rebuild_packing(names)

    def _rebuild_packing(self, new_order: list[str]):
        """Repack all tab widgets in *new_order*, rebuilding separators."""
        for w in self._tabs.values():
            if w["sep"]:
                w["sep"].pack_forget()
            w["button"].pack_forget()
            w["close"].pack_forget()

        new_tabs: dict[str, dict] = {}
        for i, name in enumerate(new_order):
            w = self._tabs[name]
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
        was_drag = self._drag_active
        self._drag_active = False
        if not was_drag:
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
        for name, widgets in self._tabs.items():
            bg = self._tab_bg(name)
            widgets["button"].config(relief="flat", bg=bg)
            widgets["close"].config(relief="flat", bg=bg)
