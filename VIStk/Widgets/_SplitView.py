from __future__ import annotations

from tkinter import Frame, ttk


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

    def __init__(self, parent, host=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._host = host
        self._callbacks: dict = {}

        # Import here to avoid circular import at module level
        from VIStk.Objects._TabManager import TabManager

        # Start with a single TabManager leaf
        self._root_widget: TabManager | _SplitNode = TabManager(self)
        self._root_widget.pack(fill="both", expand=True)
        self._focused_pane: TabManager = self._root_widget

        # Map each TabManager to its parent _SplitNode (None for root leaf)
        self._pane_parents: dict[int, _SplitNode | None] = {
            id(self._root_widget): None
        }

        self._wire_pane(self._root_widget)

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

    def split(self, pane, direction: str):
        """Split *pane* into two side-by-side panes.

        All existing tabs are transferred to the first (left / top) pane.
        The second (right / bottom) pane starts empty.

        ``ttk.PanedWindow`` requires its children to be direct Tk children,
        so both replacement panes are created fresh as children of the
        PanedWindow.  The old *pane* is destroyed after its tabs are
        transferred.

        Args:
            pane:      The ``TabManager`` to split.
            direction: ``"right"`` for horizontal or ``"down"`` for vertical.

        Returns:
            ``(left_pane, right_pane)`` — the two new ``TabManager`` instances.
            *left_pane* contains all tabs that were in *pane*.
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

        # Replace pane with the new node in its parent
        if parent_node is None:
            pane.pack_forget()
            self._root_widget = node
            node.pack(fill="both", expand=True)
        else:
            parent_node.replace_child(pane, node)

        # Both new panes must be Tk children of the PanedWindow
        left_pane = TabManager(node.paned)
        right_pane = TabManager(node.paned)
        node.set_slot1(left_pane)
        node.set_slot2(right_pane)

        self._pane_parents[id(node)] = parent_node
        self._pane_parents[id(left_pane)] = node
        self._pane_parents[id(right_pane)] = node
        self._wire_pane(left_pane)
        self._wire_pane(right_pane)

        # Transfer existing tabs from old pane to left_pane (re-runs setup)
        for tab_name in list(pane._tabs.keys()):
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
                except Exception:
                    pass
            try:
                pane._tabs[tab_name]["frame"].destroy()
            except Exception:
                pass
        pane._tabs.clear()
        del self._pane_parents[id(pane)]
        try:
            pane.destroy()
        except Exception:
            pass

        # Update focused pane if it was the old one
        if self._focused_pane is pane:
            self._focused_pane = left_pane

        # Set sash to 50/50 after geometry is computed
        node.paned.after_idle(lambda: self._set_sash_midpoint(node))

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

        # Track whether the focused pane was the one being removed
        # or lives inside the sibling subtree
        old_focused = self._focused_pane
        focused_was_removed = (old_focused is pane)

        # Collect tab data from sibling subtree BEFORE destroying anything
        sibling_snapshot = self._snapshot_subtree(sibling)

        # Remove all old tracking for the parent_node's entire subtree
        self._remove_tracking(parent_node)

        # Destroy the entire parent_node (both panes + the PanedWindow)
        try:
            parent_node.pack_forget()
        except Exception:
            pass
        try:
            parent_node.destroy()
        except Exception:
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
            grandparent_node.replace_child_fresh(rebuilt)
            self._pane_parents[id(rebuilt)] = grandparent_node
            if isinstance(rebuilt, _SplitNode):
                self._update_parent_tracking(rebuilt, grandparent_node)

        # Restore focus
        if focused_was_removed:
            panes = self.all_tab_managers()
            self._focused_pane = panes[0] if panes else None
        else:
            # Try to find the rebuilt version of the previously focused pane
            # by matching the active tab name
            panes = self.all_tab_managers()
            if old_focused is not None and hasattr(old_focused, '_active'):
                active_name = old_focused._active
                for p in panes:
                    if active_name and active_name in p._tabs:
                        self._focused_pane = p
                        break
                else:
                    self._focused_pane = panes[0] if panes else None
            else:
                self._focused_pane = panes[0] if panes else None

        # Update visual focus indicators (single pane = always focused)
        self._update_focused_styles()

    # ── Internal ──────────────────────────────────────────────────────────────

    def _wire_pane(self, pane):
        """Wire callbacks and focus tracking on a TabManager."""
        self._apply_callbacks(pane)

        # Track focus: clicking in the content area or activating a tab sets focus
        pane._content.bind("<Button-1>", lambda e, p=pane: self._set_focused(p), add="+")
        pane.tab_bar.bind("<Button-1>", lambda e, p=pane: self._set_focused(p), add="+")

        # Wrap on_tab_activate to also track focus.
        # Look up from self._callbacks at call time so that callbacks
        # registered after _wire_pane (via set_callbacks) are found.
        def _activate_and_focus(name, module, _pane=pane):
            self._set_focused(_pane)
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

    def _apply_callbacks(self, pane):
        """Set stored callbacks on a TabManager, excluding activate/deactivate
        which are wrapped by _wire_pane."""
        for key, fn in self._callbacks.items():
            if key not in ("on_tab_activate", "on_tab_deactivate"):
                setattr(pane, key, fn)

    def _set_focused(self, pane):
        """Set *pane* as the focused pane and update visual indicators."""
        if id(pane) not in self._pane_parents:
            return
        self._focused_pane = pane
        self._update_focused_styles()

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

    def _reparent_widget(self, widget, new_parent):
        """Move a widget to a new parent using Tk's internal reparenting."""
        from VIStk.Objects._TabManager import TabManager
        if isinstance(widget, (Frame, TabManager)):
            try:
                widget.pack_forget()
            except Exception:
                pass
            try:
                widget.place_forget()
            except Exception:
                pass
            # Tk reparent via the internal _w command is unreliable across
            # platforms.  Instead we just forget from old parent and the
            # caller must re-pack/re-add to the new parent's geometry manager.
            # For PanedWindow children the caller uses paned.add().
            pass

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
        except Exception:
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
        except Exception:
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
        except Exception:
            idx = None

        try:
            old_child.pack_forget()
        except Exception:
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
            except Exception:
                pass
            self.paned.add(new_child, weight=1)
            self.paned.add(self.slot2, weight=1)
        else:
            self.paned.add(new_child, weight=1)
