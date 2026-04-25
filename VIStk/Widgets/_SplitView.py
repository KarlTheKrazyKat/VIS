from __future__ import annotations

from tkinter import Frame, Toplevel, TclError, ttk


class SplitView(Frame):
    """A tree-of-panes container for the Host window's content area.

    ``SplitView`` starts with a single :class:`TabManager` leaf.  Calling
    :meth:`split` replaces a leaf with a ``ttk.PanedWindow`` that holds the
    original pane and a fresh empty pane.  The tree can be split recursively.

    When a pane's last tab is removed (closed or dragged away), the pane
    collapses immediately — the parent ``PanedWindow`` is dissolved and the
    surviving sibling is promoted.

    Attributes:
        focused_pane (TabManager): The pane the user last interacted with.
    """

    _registry: list["SplitView"] = []
    _global_focused_pane = None  # last-focused pane across all windows

    def __init__(self, parent, host=None, tab_position: str = "top", **kwargs):
        super().__init__(parent, **kwargs)
        self._host = host
        self._callbacks: dict = {}
        self._tab_position: str = tab_position

        # Import here to avoid circular import at module level
        from VIStk.Objects._TabManager import TabManager

        # Start with a single TabManager leaf
        self._root_widget: TabManager | _SplitNode = TabManager(self, position=tab_position)
        self._root_widget.pack(fill="both", expand=True)
        self._focused_pane: TabManager = self._root_widget

        # Map each TabManager to its parent _SplitNode (None for root leaf)
        self._pane_parents: dict[int, _SplitNode | None] = {
            id(self._root_widget): None
        }

        self._wire_pane(self._root_widget)

        # Drop-zone overlay (semi-transparent Toplevel shown during drag)
        self._drop_overlay: Toplevel | None = None
        self._drop_zone_info: tuple | None = None  # (pane, direction)

        SplitView._registry.append(self)

    def destroy(self):
        try:
            SplitView._registry.remove(self)
        except ValueError:
            pass
        if SplitView._global_focused_pane is not None:
            try:
                if not SplitView._global_focused_pane.winfo_exists():
                    SplitView._global_focused_pane = None
            except Exception:
                SplitView._global_focused_pane = None
        super().destroy()

    # ── Cross-window helpers ─────────────────────────────────────────────────

    @classmethod
    def find_owner(cls, pane) -> "SplitView | None":
        """Return the SplitView that owns *pane*, or ``None``."""
        for sv in cls._registry:
            if id(pane) in sv._pane_parents:
                return sv
        return None

    @classmethod
    def detect_any_drop_zone(cls, x_root: int, y_root: int):
        """Check all SplitViews for a split drop zone.

        When windows overlap, only the frontmost window at the cursor
        position is considered (uses Tk stacking order).

        Returns ``(splitview, pane, direction)`` or ``None``.
        """
        if not cls._registry:
            return None

        # Get Tk stacking order (bottom to top) to resolve overlaps
        try:
            stack = cls._registry[0].tk.call(
                'wm', 'stackorder', cls._registry[0].winfo_toplevel())
            if isinstance(stack, str):
                stack = stack.split()
            else:
                stack = list(stack)
        except TclError:
            stack = []
        stack_rank = {str(path): i for i, path in enumerate(stack)}

        # Sort SplitViews by stacking order — frontmost first
        def _rank(sv):
            try:
                return stack_rank.get(str(sv.winfo_toplevel()), -1)
            except TclError:
                return -1

        sorted_svs = sorted(cls._registry, key=_rank, reverse=True)

        for sv in sorted_svs:
            # Only consider if cursor is within this window's client area
            try:
                tl = sv.winfo_toplevel()
                wx = tl.winfo_rootx()
                wy = tl.winfo_rooty()
                ww = tl.winfo_width()
                wh = tl.winfo_height()
                if not (wx <= x_root < wx + ww and wy <= y_root < wy + wh):
                    continue
            except TclError:
                continue
            result = sv.detect_drop_zone(x_root, y_root)
            if result:
                return (sv, result[0], result[1])
            # Cursor is in this window but not in a drop zone — stop checking
            return None
        return None

    @classmethod
    def lift_window_at(cls, x_root: int, y_root: int):
        """Lift the SplitView window under the cursor to the front.

        Called during drag motion so the target window comes to the
        front as soon as the cursor moves over it.  If multiple
        windows overlap at the cursor position, no lift is performed
        (the frontmost one stays on top).
        """
        if not cls._registry:
            return
        # Find all SplitView windows whose client area contains the cursor
        hits = []
        for sv in cls._registry:
            try:
                tl = sv.winfo_toplevel()
                wx = tl.winfo_rootx()
                wy = tl.winfo_rooty()
                ww = tl.winfo_width()
                wh = tl.winfo_height()
                if wx <= x_root < wx + ww and wy <= y_root < wy + wh:
                    hits.append(tl)
            except TclError:
                continue
        if len(hits) == 1:
            # Only one window at this position — bring it to front
            hits[0].lift()
        # Multiple windows overlap — respect z-order, don't lift

    @classmethod
    def hide_all_overlays(cls):
        """Hide drop-zone overlays on every SplitView."""
        for sv in cls._registry:
            sv.hide_drop_overlay()

    @staticmethod
    def global_drag_zone_handler(action: str, x: int, y: int):
        """Standalone ``on_drag_zone`` callback usable by any TabBar.

        Checks all registered SplitViews.  Suitable for TabBars that
        live outside a SplitView (e.g. in a DetachedWindow).
        """
        if action == "hide":
            SplitView.hide_all_overlays()
            return None
        if action == "check":
            SplitView.lift_window_at(x, y)
            result = SplitView.detect_any_drop_zone(x, y)
            if result:
                sv, pane, direction = result
                for other in SplitView._registry:
                    if other is not sv:
                        other.hide_drop_overlay()
                sv.show_drop_overlay(pane, direction)
            else:
                SplitView.hide_all_overlays()
            return None
        if action == "drop":
            SplitView.hide_all_overlays()
            result = SplitView.detect_any_drop_zone(x, y)
            if result:
                sv, pane, direction = result
                return (pane, direction)
            return None
        return None

    # ── Public API ────────────────────────────────────────────────────────────

    @property
    def focused_pane(self):
        """The :class:`TabManager` the user last interacted with."""
        # Ensure the focused pane is still alive
        if self._focused_pane is not None and id(self._focused_pane) in self._pane_parents:
            return self._focused_pane
        # Fallback to first available pane
        panes = self.all_tab_managers()
        if panes:
            self._focused_pane = panes[0]
            return self._focused_pane
        return None

    def set_callbacks(self, callbacks: dict):
        """Store callback dict and apply to all current panes.

        Keys are attribute names on ``TabManager``: ``on_tab_activate``,
        ``on_tab_deactivate``, ``on_tab_popout``, ``on_tab_detach``,
        ``on_tab_refresh``, ``on_tab_info_change``, ``on_tab_split``.
        """
        self._callbacks = dict(callbacks)
        for pane in self.all_tab_managers():
            self._apply_callbacks(pane)

    def all_tab_managers(self) -> list:
        """Return every :class:`TabManager` leaf in the tree (left-to-right)."""
        from VIStk.Objects._TabManager import TabManager
        result = []
        self._collect_panes(self._root_widget, result, TabManager)
        return result

    def all_tabs(self) -> dict[str, dict]:
        """Aggregate ``_tabs`` from every pane into one dict."""
        merged = {}
        for pane in self.all_tab_managers():
            merged.update(pane._tabs)
        return merged

    def find_pane_for_tab(self, name: str):
        """Return the :class:`TabManager` that owns *name*, or ``None``."""
        for pane in self.all_tab_managers():
            if name in pane._tabs:
                return pane
        return None

    # ── Drag-to-split drop zones ─────────────────────────────────────────────

    _DROP_ZONE_RATIO = 0.25  # outer 25 % of the content area triggers a zone

    def detect_drop_zone(self, x_root: int, y_root: int):
        """Check if screen coords fall in a split drop zone.

        Returns ``(pane, direction)`` where *direction* is one of
        ``"right"``, ``"left"``, ``"down"``, ``"up"``; or ``None`` if the
        cursor is not in any zone.
        """
        for pane in self.all_tab_managers():
            content = pane._content
            try:
                cx = content.winfo_rootx()
                cy = content.winfo_rooty()
                cw = content.winfo_width()
                ch = content.winfo_height()
            except TclError:
                continue
            if not (cx <= x_root < cx + cw and cy <= y_root < cy + ch):
                continue
            # Cursor is inside this pane's content area
            rx = (x_root - cx) / max(cw, 1)
            ry = (y_root - cy) / max(ch, 1)
            r = self._DROP_ZONE_RATIO
            # Corners go to the nearer axis
            if rx >= 1 - r and ry >= r and ry < 1 - r:
                return pane, "right"
            if rx < r and ry >= r and ry < 1 - r:
                return pane, "left"
            if ry >= 1 - r and rx >= r and rx < 1 - r:
                return pane, "down"
            if ry < r and rx >= r and rx < 1 - r:
                return pane, "up"
            # Corners: pick dominant axis
            if rx >= 1 - r:
                return pane, "right"
            if rx < r:
                return pane, "left"
            if ry >= 1 - r:
                return pane, "down"
            if ry < r:
                return pane, "up"
            # Center — add tab to this pane
            return pane, "center"
        return None

    def show_drop_overlay(self, pane, direction: str):
        """Show a translucent overlay on the half of *pane* that would
        receive the dropped tab."""
        content = pane._content
        try:
            cx = content.winfo_rootx()
            cy = content.winfo_rooty()
            cw = content.winfo_width()
            ch = content.winfo_height()
        except TclError:
            return
        # Compute overlay rectangle (screen coords)
        if direction == "right":
            ox, oy, ow, oh = cx + cw // 2, cy, cw // 2, ch
        elif direction == "left":
            ox, oy, ow, oh = cx, cy, cw // 2, ch
        elif direction == "down":
            ox, oy, ow, oh = cx, cy + ch // 2, cw, ch // 2
        elif direction == "up":
            ox, oy, ow, oh = cx, cy, cw, ch // 2
        elif direction == "center":
            ox, oy, ow, oh = cx, cy, cw, ch
        else:
            return
        info = (id(pane), direction)
        if self._drop_zone_info == info and self._drop_overlay is not None:
            return  # already showing the right overlay
        self.hide_drop_overlay()
        self._drop_zone_info = info
        overlay = Toplevel(self)
        overlay.overrideredirect(True)
        overlay.attributes("-alpha", 0.22)
        overlay.attributes("-topmost", True)
        overlay.configure(bg="dodger blue")
        overlay.geometry(f"{ow}x{oh}+{ox}+{oy}")
        self._drop_overlay = overlay
        # Show insertion indicator in target pane's tab bar for center drops
        self._drop_indicator_pane = None
        if direction == "center":
            try:
                n = len(pane.tab_bar._tabs)
                pane.tab_bar.set_insert_indicator(n)
                self._drop_indicator_pane = pane
            except TclError:
                pass

    def hide_drop_overlay(self):
        """Destroy the drop-zone overlay if visible."""
        if getattr(self, "_drop_indicator_pane", None) is not None:
            try:
                self._drop_indicator_pane.tab_bar.clear_insert_indicator()
            except TclError:
                pass
            self._drop_indicator_pane = None
        if self._drop_overlay is not None:
            try:
                self._drop_overlay.destroy()
            except TclError:
                pass
            self._drop_overlay = None
            self._drop_zone_info = None

    def get_drop_zone_info(self):
        """Return the current ``(pane, direction)`` or ``None``."""
        return self._drop_zone_info

    def split(self, pane, direction: str, exclude: set | None = None):
        """Split *pane* into two side-by-side panes.

        Tabs in *pane* are transferred to the first (left / top) pane,
        except any names listed in *exclude* which are silently skipped
        (the caller is responsible for placing them elsewhere).

        ``ttk.PanedWindow`` requires its children to be direct Tk children,
        so both replacement panes are created fresh as children of the
        PanedWindow.  The old *pane* is destroyed after its tabs are
        transferred.

        Args:
            pane:      The ``TabManager`` to split.
            direction: ``"right"`` for horizontal or ``"down"`` for vertical.
            exclude:   Tab names to skip during transfer (optional).

        Returns:
            ``(left_pane, right_pane)`` — the two new ``TabManager`` instances.
            *left_pane* contains all tabs that were in *pane* minus *exclude*.
        """
        from VIStk.Objects._TabManager import TabManager

        orient = "horizontal" if direction == "right" else "vertical"
        parent_node = self._pane_parents.get(id(pane))

        # Create a _SplitNode to replace the pane
        if parent_node is None:
            container = self
        else:
            container = parent_node.paned

        node = _SplitNode(container, orient=orient)

        # Save parent sash position before replacing (it will shift)
        parent_sash_pos = None
        if parent_node is not None:
            try:
                parent_node.paned.update_idletasks()
                parent_sash_pos = parent_node.paned.sashpos(0)
            except TclError:
                pass

        # Replace pane with the new node in its parent
        if parent_node is None:
            pane.pack_forget()
            self._root_widget = node
            node.pack(fill="both", expand=True)
        else:
            parent_node.replace_child(pane, node)

        # Both new panes must be Tk children of the PanedWindow
        left_pane = TabManager(node.paned, position=self._tab_position)
        right_pane = TabManager(node.paned, position=self._tab_position)
        node.set_slot1(left_pane)
        node.set_slot2(right_pane)

        self._pane_parents[id(node)] = parent_node
        self._pane_parents[id(left_pane)] = node
        self._pane_parents[id(right_pane)] = node
        self._wire_pane(left_pane)
        self._wire_pane(right_pane)

        # Transfer existing tabs from old pane to left_pane (re-runs setup)
        _exclude = exclude or set()
        for tab_name in list(pane._tabs.keys()):
            if tab_name in _exclude:
                continue
            entry = pane._tabs[tab_name]
            module    = entry.get("module")
            hooks     = entry.get("hooks")
            icon      = entry.get("icon")
            base_name = entry.get("base_name", tab_name)
            info_data = entry.get("_info_trace")  # (StringVar, tid) or None
            info_str  = entry.get("info", "")

            left_pane.open_tab(tab_name, module, hooks=hooks, icon=icon,
                               base_name=base_name)

            # Restore tab info (prefer StringVar if traced)
            if info_data is not None:
                var, _ = info_data
                left_pane.set_tab_info(tab_name, var)
            elif info_str:
                left_pane.set_tab_info(tab_name, info_str)

        # Clean up old pane without triggering callbacks
        for tab_name in list(pane._tabs.keys()):
            trace_info = pane._tabs[tab_name].get("_info_trace")
            if trace_info is not None:
                var, tid = trace_info
                try:
                    var.trace_remove("write", tid)
                except TclError:
                    pass
            try:
                pane._tabs[tab_name]["frame"].destroy()
            except TclError:
                pass
        pane._tabs.clear()
        del self._pane_parents[id(pane)]
        try:
            pane.destroy()
        except TclError:
            pass

        # Update focused pane if it was the old one
        if self._focused_pane is pane:
            self._focused_pane = left_pane

        # Set new split sash to 50/50 and restore parent sash
        def _fix_sashes():
            self._set_sash_midpoint(node)
            if parent_sash_pos is not None and parent_node is not None:
                try:
                    parent_node.paned.sashpos(0, parent_sash_pos)
                except TclError:
                    pass
        node.paned.after_idle(_fix_sashes)

        # Update visual focus indicators
        self._update_focused_styles()

        return left_pane, right_pane

    def remove_pane(self, pane):
        """Collapse *pane* out of the tree, promoting the surviving sibling.

        Because ``ttk.PanedWindow`` requires widgets to be direct Tk
        children, the surviving sibling (and its entire subtree) is
        rebuilt under the correct parent.  If only one pane remains
        (the root), this is a no-op.
        """
        from VIStk.Objects._TabManager import TabManager

        parent_node = self._pane_parents.get(id(pane))
        if parent_node is None:
            # This is the root — can't remove the last pane
            return

        sibling = parent_node.other_child(pane)
        grandparent_node = self._pane_parents.get(id(parent_node))

        # Determine the Tk parent for the rebuilt sibling
        if grandparent_node is None:
            tk_parent = self
        else:
            tk_parent = grandparent_node.paned

        # Remember which slot parent_node occupied in grandparent
        grandparent_slot = None
        if grandparent_node is not None:
            if grandparent_node.slot1 is parent_node:
                grandparent_slot = 1
            else:
                grandparent_slot = 2

        # Track whether the focused pane was the one being removed
        # or lives inside the sibling subtree
        old_focused = self._focused_pane
        focused_was_removed = (old_focused is pane)

        # Collect tab data from sibling subtree BEFORE destroying anything
        sibling_snapshot = self._snapshot_subtree(sibling)

        # Remove all old tracking for the parent_node's entire subtree
        self._remove_tracking(parent_node)

        # Remove parent_node from grandparent's PanedWindow before destroying
        if grandparent_node is not None:
            try:
                grandparent_node.paned.forget(parent_node)
            except TclError:
                pass

        # Destroy the entire parent_node (both panes + the PanedWindow)
        try:
            parent_node.pack_forget()
        except TclError:
            pass
        try:
            parent_node.destroy()
        except TclError:
            pass

        # Rebuild the surviving sibling under the correct Tk parent
        rebuilt = self._rebuild_from_snapshot(sibling_snapshot, tk_parent)

        # Place the rebuilt widget
        if grandparent_node is None:
            self._root_widget = rebuilt
            rebuilt.pack(fill="both", expand=True)
            self._pane_parents[id(rebuilt)] = None
            if isinstance(rebuilt, _SplitNode):
                self._update_parent_tracking(rebuilt, None)
        else:
            # Replace the correct slot in the grandparent
            if grandparent_slot == 1:
                grandparent_node.slot1 = rebuilt
            else:
                grandparent_node.slot2 = rebuilt
            # Re-add both slots to the PanedWindow in correct order
            grandparent_node.replace_child_fresh(rebuilt)
            self._pane_parents[id(rebuilt)] = grandparent_node
            if isinstance(rebuilt, _SplitNode):
                self._update_parent_tracking(rebuilt, grandparent_node)

        # Restore focus
        # The rebuilt subtree contains all surviving panes; pick the first one.
        # Name-based matching is avoided here — that is deferred to the tab-ID
        # refactor planned for 0.4.6.
        panes = self.all_tab_managers()
        self._focused_pane = panes[0] if panes else None

        # Update visual focus indicators (single pane = always focused)
        self._update_focused_styles()

    # ── Internal ──────────────────────────────────────────────────────────────

    def _on_window_focus_out(self, event):
        """Dim all pane focus indicators when the window loses OS focus."""
        # Only act if focus left this specific toplevel
        if event.widget is not self.winfo_toplevel():
            return
        for pane in self.all_tab_managers():
            pane.tab_bar.set_focused_style(False)

    def _on_window_focus_in(self, event):
        """Restore focused pane indicator when the window regains OS focus."""
        if event.widget is not self.winfo_toplevel():
            return
        self._update_focused_styles()

    def _focus_from_click(self, event):
        """Walk up from clicked widget to find the owning pane and focus it."""
        panes = {id(tm): tm for tm in self.all_tab_managers()}
        w = event.widget
        try:
            while w is not None:
                if id(w) in panes:
                    self._set_focused(panes[id(w)])
                    return
                w = w.master
        except TclError:
            pass

    def _wire_pane(self, pane):
        """Wire callbacks and focus tracking on a TabManager."""
        self._apply_callbacks(pane)

        # Track focus: clicking anywhere inside a pane sets focus.
        # Bind on the toplevel so descendant widget clicks are caught.
        if not getattr(self, "_toplevel_click_bound", False):
            self._toplevel_click_bound = True
            tl = self.winfo_toplevel()
            tl.bind("<Button-1>", self._focus_from_click, add="+")
            tl.bind("<FocusOut>", self._on_window_focus_out, add="+")
            tl.bind("<FocusIn>", self._on_window_focus_in, add="+")
        pane._content.bind("<Button-1>", lambda e, p=pane: self._set_focused(p), add="+")
        pane.tab_bar.bind("<Button-1>", lambda e, p=pane: self._set_focused(p), add="+")

        # Wrap on_tab_activate to also track focus.
        # Look up from self._callbacks at call time so that callbacks
        # registered after _wire_pane (via set_callbacks) are found.
        def _activate_and_focus(name, module, _pane=pane):
            self._set_focused(_pane, _skip_activate=True)
            orig = self._callbacks.get("on_tab_activate")
            if orig:
                orig(name, module)

        pane.on_tab_activate = _activate_and_focus

        # Wire the empty-pane detection: when all tabs are closed, auto-collapse
        def _deactivate_and_check(name, _pane=pane):
            orig = self._callbacks.get("on_tab_deactivate")
            if orig:
                orig(name)
            # If name is None, all tabs are gone — collapse this pane
            if name is None and len(_pane._tabs) == 0:
                parent_node = self._pane_parents.get(id(_pane))
                if parent_node is not None:
                    # Schedule collapse to avoid modifying widget tree mid-callback
                    _pane.after_idle(lambda: self.remove_pane(_pane))

        pane.on_tab_deactivate = _deactivate_and_check

        # Wire drag-to-split zone detection (closure captures source pane)
        pane.tab_bar.on_drag_zone = lambda action, x, y, _p=pane: \
            self._handle_drag_zone(action, x, y, _p)

    def _handle_drag_zone(self, action: str, x: int, y: int,
                          source_pane=None):
        """Callback for TabBar drag zone detection.

        Checks **all** registered SplitViews so cross-window drops work.

        *action* is ``"check"`` (show/hide overlay) or ``"drop"``
        (returns ``(pane, direction)`` if valid, else ``None``).
        *source_pane* is the TabManager the drag originated from.
        """
        if action == "hide":
            SplitView.hide_all_overlays()
            return None

        if action == "check":
            SplitView.lift_window_at(x, y)
            result = SplitView.detect_any_drop_zone(x, y)
            if result:
                sv, pane, direction = result
                # Single tab dragged over its own pane — show center instead
                if direction != "center" and pane is source_pane:
                    if len(pane._tabs) <= 1:
                        direction = "center"
                # Hide other overlays, show on the correct SplitView
                for other in SplitView._registry:
                    if other is not sv:
                        other.hide_drop_overlay()
                sv.show_drop_overlay(pane, direction)
            else:
                SplitView.hide_all_overlays()
            return None

        if action == "drop":
            SplitView.hide_all_overlays()
            result = SplitView.detect_any_drop_zone(x, y)
            if result:
                sv, pane, direction = result
                if direction != "center" and pane is source_pane:
                    if len(pane._tabs) <= 1:
                        direction = "center"
                return (pane, direction)
            return None

        return None

    def _apply_callbacks(self, pane):
        """Set stored callbacks on a TabManager, excluding activate/deactivate
        which are wrapped by _wire_pane."""
        for key, fn in self._callbacks.items():
            if key not in ("on_tab_activate", "on_tab_deactivate"):
                setattr(pane, key, fn)

    def _set_focused(self, pane, _skip_activate=False):
        """Set *pane* as the focused pane and update visual indicators.

        When focus moves to a different pane, fires the activate callback
        for the new pane's active tab so the menu bar updates.  The
        ``_skip_activate`` flag is set by ``_activate_and_focus`` which
        fires the callback itself to avoid a double-fire.
        """
        if id(pane) not in self._pane_parents:
            return
        old = self._focused_pane
        if pane is old and SplitView._global_focused_pane is pane:
            return
        self._focused_pane = pane
        SplitView._global_focused_pane = pane
        self._update_focused_styles()
        # Re-fire activate for the new pane's active tab to update menu bar
        if (not _skip_activate and pane is not old
                and pane._active and pane._active in pane._tabs):
            entry = pane._tabs[pane._active]
            on_activate = self._callbacks.get("on_tab_activate")
            if on_activate:
                on_activate(pane._active, entry.get("module"))

    def _update_focused_styles(self):
        """Highlight the focused pane's tab bar and dim the others."""
        panes = self.all_tab_managers()
        if len(panes) <= 1:
            # Single pane — always show as focused (no split active)
            for p in panes:
                p.tab_bar.set_focused_style(True)
            return
        for p in panes:
            p.tab_bar.set_focused_style(p is self._focused_pane)

    def _collect_panes(self, widget, result, tm_class):
        """Recursively collect all TabManager leaves."""
        if isinstance(widget, tm_class):
            result.append(widget)
        elif isinstance(widget, _SplitNode):
            if widget.slot1 is not None:
                self._collect_panes(widget.slot1, result, tm_class)
            if widget.slot2 is not None:
                self._collect_panes(widget.slot2, result, tm_class)

    def _snapshot_subtree(self, widget):
        """Recursively snapshot a subtree's data for later rebuild.

        Returns a dict describing the tree structure and tab data so
        the subtree can be destroyed and rebuilt under a new Tk parent.
        """
        from VIStk.Objects._TabManager import TabManager

        if isinstance(widget, TabManager):
            tabs = []
            for tab_name in list(widget._tabs.keys()):
                entry = widget._tabs[tab_name]
                tab_data = {
                    "name": tab_name,
                    "module": entry.get("module"),
                    "hooks": entry.get("hooks"),
                    "icon": entry.get("icon"),
                    "base_name": entry.get("base_name", tab_name),
                    "info_str": entry.get("info", ""),
                }
                # Capture StringVar value if traced (can't keep the var across destroy)
                info_trace = entry.get("_info_trace")
                if info_trace is not None:
                    var, _ = info_trace
                    try:
                        tab_data["info_str"] = var.get()
                    except TclError:
                        pass
                tabs.append(tab_data)
            return {
                "type": "leaf",
                "tabs": tabs,
                "is_focused": widget is self._focused_pane,
                "active": widget._active,
            }
        elif isinstance(widget, _SplitNode):
            return {
                "type": "node",
                "orient": widget.orient,
                "slot1": self._snapshot_subtree(widget.slot1) if widget.slot1 else None,
                "slot2": self._snapshot_subtree(widget.slot2) if widget.slot2 else None,
            }
        return {"type": "leaf", "tabs": [], "is_focused": False, "active": None}

    def _remove_tracking(self, widget):
        """Recursively remove all _pane_parents entries for a subtree."""
        self._pane_parents.pop(id(widget), None)
        if isinstance(widget, _SplitNode):
            if widget.slot1 is not None:
                self._remove_tracking(widget.slot1)
            if widget.slot2 is not None:
                self._remove_tracking(widget.slot2)

    def _rebuild_from_snapshot(self, snapshot, tk_parent):
        """Recreate a subtree from snapshot data under the correct Tk parent.

        Returns the rebuilt root widget (TabManager or _SplitNode).
        """
        from VIStk.Objects._TabManager import TabManager

        if snapshot["type"] == "leaf":
            pane = TabManager(tk_parent, position=self._tab_position)
            self._wire_pane(pane)
            # Re-open all tabs
            for tab_data in snapshot["tabs"]:
                pane.open_tab(
                    tab_data["name"],
                    tab_data["module"],
                    hooks=tab_data.get("hooks"),
                    icon=tab_data.get("icon"),
                    base_name=tab_data.get("base_name", tab_data["name"]),
                )
                if tab_data.get("info_str"):
                    pane.set_tab_info(tab_data["name"], tab_data["info_str"])
            # Track focus
            if snapshot.get("is_focused"):
                self._focused_pane = pane
            return pane

        elif snapshot["type"] == "node":
            node = _SplitNode(tk_parent, orient=snapshot["orient"])
            # Rebuild children as Tk children of the node's PanedWindow
            if snapshot["slot1"] is not None:
                child1 = self._rebuild_from_snapshot(snapshot["slot1"], node.paned)
                node.set_slot1(child1)
                self._pane_parents[id(child1)] = node
                if isinstance(child1, _SplitNode):
                    self._update_parent_tracking(child1, node)
            if snapshot["slot2"] is not None:
                child2 = self._rebuild_from_snapshot(snapshot["slot2"], node.paned)
                node.set_slot2(child2)
                self._pane_parents[id(child2)] = node
                if isinstance(child2, _SplitNode):
                    self._update_parent_tracking(child2, node)
            # Set sash to 50/50
            node.paned.after_idle(lambda n=node: self._set_sash_midpoint(n))
            return node

        return None

    def _update_parent_tracking(self, widget, parent_node):
        """Update _pane_parents for *widget* and its subtree."""
        from VIStk.Objects._TabManager import TabManager
        if isinstance(widget, TabManager):
            self._pane_parents[id(widget)] = parent_node
        elif isinstance(widget, _SplitNode):
            self._pane_parents[id(widget)] = parent_node
            if widget.slot1 is not None:
                self._update_parent_tracking(widget.slot1, widget)
            if widget.slot2 is not None:
                self._update_parent_tracking(widget.slot2, widget)

    def _set_sash_midpoint(self, node: "_SplitNode"):
        """Position the sash at 50% of the PanedWindow."""
        try:
            node.paned.update_idletasks()
            if node.orient == "horizontal":
                total = node.paned.winfo_width()
            else:
                total = node.paned.winfo_height()
            if total > 1:
                node.paned.sashpos(0, total // 2)
        except TclError:
            pass


class _SplitNode(Frame):
    """Internal node in the split tree — wraps a ``ttk.PanedWindow``.

    Each node has exactly two children (``slot1`` and ``slot2``), each of
    which is either a :class:`TabManager` or another ``_SplitNode``.
    """

    def __init__(self, parent, orient: str = "horizontal", **kwargs):
        super().__init__(parent, **kwargs)
        self.orient = orient
        self.paned = ttk.PanedWindow(self, orient=orient)
        self.paned.pack(fill="both", expand=True)
        self.slot1 = None
        self.slot2 = None

    def set_slot1(self, widget):
        """Place *widget* in the first (left / top) slot."""
        self.slot1 = widget
        # Reparent widget into the PanedWindow
        try:
            widget.pack_forget()
        except TclError:
            pass
        self.paned.add(widget, weight=1)

    def set_slot2(self, widget):
        """Place *widget* in the second (right / bottom) slot."""
        self.slot2 = widget
        self.paned.add(widget, weight=1)

    def other_child(self, child):
        """Return the sibling of *child*."""
        if child is self.slot1:
            return self.slot2
        return self.slot1

    def replace_child(self, old_child, new_child):
        """Replace *old_child* with *new_child* in the PanedWindow."""
        try:
            # Get the position of old_child in the paned window
            panes = list(self.paned.panes())
            idx = None
            old_name = str(old_child)
            for i, p in enumerate(panes):
                if p == old_name:
                    idx = i
                    break

            self.paned.forget(old_child)
        except TclError:
            idx = None

        try:
            old_child.pack_forget()
        except TclError:
            pass

        if self.slot1 is old_child:
            self.slot1 = new_child
        elif self.slot2 is old_child:
            self.slot2 = new_child

        # Insert at correct position
        if idx == 0 and self.slot2 is not None:
            # New child should be first — remove slot2, add new, re-add slot2
            try:
                self.paned.forget(self.slot2)
            except TclError:
                pass
            self.paned.add(new_child, weight=1)
            self.paned.add(self.slot2, weight=1)
        else:
            self.paned.add(new_child, weight=1)

    def replace_child_fresh(self, new_child):
        """Replace whichever slot is missing/destroyed with *new_child*.

        Used by ``remove_pane`` after rebuilding a subtree: the old slots
        have been destroyed, and *new_child* is already a proper Tk child
        of ``self.paned``.  Clears the PanedWindow and re-adds both slots.
        """
        # Figure out which slot still exists vs which was destroyed
        # After a rebuild, the caller sets slot tracking before calling this
        # Just clear and re-add both slots in order
        try:
            for p in list(self.paned.panes()):
                self.paned.forget(p)
        except TclError:
            pass

        if self.slot1 is not None:
            self.paned.add(self.slot1, weight=1)
        if self.slot2 is not None:
            self.paned.add(self.slot2, weight=1)

