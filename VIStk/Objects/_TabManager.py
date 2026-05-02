from __future__ import annotations

import gc
import inspect
import queue
import sys
from tkinter import Frame

from VIStk.Objects._Identity import new_id
from VIStk.Widgets._TabBar import TabBar, _BG_BAR


def set_tab_info(frame, info):
    """Set the characteristic info string for the tab that owns *frame*.

    Call this from within a screen's ``setup(parent)`` function.  ``info``
    may be a plain ``str`` (set once) or a ``tkinter.StringVar`` (traced; the
    tab label and window title update automatically whenever the variable
    changes).

    Example::

        def setup(parent):
            from VIStk.Objects import set_tab_info
            from tkinter import StringVar
            wo_var = StringVar(value="")
            set_tab_info(parent, wo_var)
            ...
    """
    mgr    = getattr(frame, "_vis_tab_manager", None)
    tab_id = getattr(frame, "_vis_tab_id",      None)
    if mgr is not None and tab_id is not None:
        mgr.set_tab_info(tab_id, info)


class TabManager(Frame):
    """Manages the tabbed screen area of a DetachedWindow.

    ``TabManager`` is a ``Frame`` that fills its parent.  It owns two child
    frames:

    * ``tab_bar`` — a :class:`~VIStk.Widgets._TabBar.TabBar` packed along
      the top edge.
    * The *content frame* (internal) — fills the remaining space.

    Tab identity (0.4.7)
    --------------------
    Every opened tab is keyed by a stable integer ``tab_id`` allocated from
    :func:`VIStk.Objects._Identity.new_id`.  Display labels are mutable
    (see :meth:`set_tab_info`) and may collide; IDs disambiguate across
    panes and windows.

    Public methods accept either an ``int`` tab ID or a ``str`` display
    label.  When a label is passed, the first matching tab is used —
    lookup is non-deterministic in the presence of duplicate labels.
    Callers that hold a specific instance should pass the ID.

    Hook lookup priority: if ``modules/<screen>/m_<screen>.py`` exists,
    ``TabManager`` checks it first for ``on_focused``, ``on_unfocused``, and
    ``configure_menu``.  The screen module is used as a fallback.

    Callbacks (receive ``tab_id: int`` as the first argument)::

        manager.on_tab_activate    = lambda tab_id, mod: ...
        manager.on_tab_deactivate  = lambda tab_id | None: ...
        manager.on_tab_popout      = lambda tab_id: ...
        manager.on_tab_detach      = lambda tab_id: ...
        manager.on_tab_refresh     = lambda tab_id: ...
        manager.on_tab_info_change = lambda tab_id, info: ...
        manager.on_tab_split       = lambda tab_id, direction, target_pane: ...

    Use :meth:`display_name` to resolve a ``tab_id`` back to its label.
    """

    def __init__(self, parent, position: str = "top", menubar=None, **kwargs):
        kwargs.setdefault("bg", _BG_BAR)
        super().__init__(parent, **kwargs)

        self.id: int = new_id()
        """Stable process-unique pane ID (0.4.7)."""

        self._tabs: dict[int, dict] = {}
        """tab_id -> {tab_id, display_name, frame, module, hooks, icon, base_name, info, _info_trace}"""
        self._active: int | None = None
        self._position: str = position

        self._action_queue: queue.SimpleQueue = queue.SimpleQueue()
        self._action_pump_id: str | None = None
        self._menubar = menubar
        self._detached_window = None

        self.on_tab_activate   = None
        self.on_tab_deactivate = None
        self.on_tab_popout     = None
        self.on_tab_detach     = None
        self.on_tab_refresh    = None
        self.on_tab_info_change = None
        self.on_tab_split      = None

        self.tab_bar = TabBar(self, position=position)
        self.tab_bar.owner = self

        self._content = Frame(self)
        self._tab_bar_hidden: bool = False
        self._repack_layout()

        self.tab_bar.on_focus_change = self._on_focus_change
        self.tab_bar.on_tab_close    = self._on_close_request
        self.tab_bar.on_tab_popout   = self._on_popout_request
        self.tab_bar.on_tab_refresh  = self._on_refresh_request
        self.tab_bar.on_drag_detach  = self._on_detach_request
        self.tab_bar.on_drag_merge   = self._on_merge_request
        self.tab_bar.on_tab_split    = self._on_split_request

        # Start the action-queue pump. Project.open() enqueues navigation
        # lambdas here; without a consumer they'd sit forever.
        self._action_pump_id = self.after(16, self._pump_actions)
        self.bind("<Destroy>", self._stop_action_pump, add="+")

    # ── Action queue pump ─────────────────────────────────────────────────────

    def _pump_actions(self):
        """Drain queued navigation callables on the Tk main loop."""
        try:
            while True:
                fn = self._action_queue.get_nowait()
                try:
                    fn()
                except Exception:
                    pass
        except queue.Empty:
            pass
        try:
            self._action_pump_id = self.after(16, self._pump_actions)
        except Exception:
            self._action_pump_id = None

    def _stop_action_pump(self, event=None):
        """Cancel the pending pump on widget destruction."""
        # <Destroy> bubbles up from descendants; only act for this widget.
        if event is not None and event.widget is not self:
            return
        if self._action_pump_id is not None:
            try:
                self.after_cancel(self._action_pump_id)
            except Exception:
                pass
            self._action_pump_id = None

    # ── Layout ─────────────────────────────────────────────────────────────────

    def _repack_layout(self):
        """Pack tab_bar and _content based on the current position setting.

        When ``_tab_bar_hidden`` is set the tab bar is omitted entirely and
        the content frame fills the pane — used by chromeless standalone
        DetachedWindows that host a single non-tabbed screen.
        """
        self.tab_bar.pack_forget()
        self._content.pack_forget()
        if not self._tab_bar_hidden:
            if self._position in ("top", "bottom"):
                self.tab_bar.pack(side=self._position, fill="x")
            else:  # left or right
                self.tab_bar.pack(side=self._position, fill="y")
        if self._position in ("top", "bottom"):
            self._content.pack(side="top", fill="both", expand=True)
        else:
            self._content.pack(side="left", fill="both", expand=True)

    def set_position(self, position: str):
        """Change the tab bar position and update the layout."""
        self._position = position
        self.tab_bar.set_position(position)
        self._repack_layout()

    def hide_tab_bar(self):
        """Hide the tab bar — used for chromeless standalone windows."""
        if not self._tab_bar_hidden:
            self._tab_bar_hidden = True
            self._repack_layout()

    def show_tab_bar(self):
        """Restore the tab bar after :meth:`hide_tab_bar`."""
        if self._tab_bar_hidden:
            self._tab_bar_hidden = False
            self._repack_layout()

    # ── Identity helpers ───────────────────────────────────────────────────────

    def _resolve_id(self, key) -> int | None:
        """Resolve *key* (int tab_id or str display label) to a tab_id."""
        if isinstance(key, int) and not isinstance(key, bool):
            return key if key in self._tabs else None
        if isinstance(key, str):
            return self._id_for_display(key)
        return None

    def _id_for_display(self, label: str) -> int | None:
        """Return the first tab_id whose display_name equals *label*, else None.

        Non-deterministic when multiple tabs share *label*.  Prefer holding
        the tab_id returned by :meth:`open_tab`.
        """
        for tab_id, entry in self._tabs.items():
            if entry.get("display_name") == label:
                return tab_id
        return None

    def display_name(self, tab_id: int) -> str | None:
        """Return the current display name of *tab_id*, or None."""
        entry = self._tabs.get(tab_id)
        return entry.get("display_name") if entry else None

    # ── Public API ─────────────────────────────────────────────────────────────

    @property
    def active(self) -> int | None:
        """Tab ID of the currently active tab (0.4.7)."""
        return self._active

    @property
    def active_module(self):
        """Return the module of the currently active tab, or None."""
        if self._active is not None and self._active in self._tabs:
            return self._tabs[self._active].get("module")
        return None

    # ── Menu delegation ───────────────────────────────────────────────────────

    def register_menu_item(self, label: str, command):
        """Register a single menu item (delegates to the window's menubar)."""
        if self._menubar:
            self._menubar.set_screen_items([{"label": label, "command": command}])

    def add_cascade(self, label: str, items: list[dict]):
        """Add a cascade menu (delegates to the window's menubar)."""
        if self._menubar:
            self._menubar.set_screen_items(items, label=label)

    # ── Navigation ────────────────────────────────────────────────────────────

    def navigate(self, name: str, args=None):
        """Navigate this pane to a new screen.

        Tears down the current screen (calling on_quit), cleans up modules,
        imports the new screen, runs setup(), and handles args.
        """
        from VIStk.Objects._Host import _HOST_INSTANCE
        if _HOST_INSTANCE is None:
            return

        # 1. Call on_quit on active screen and close it
        if self._active is not None and self._active in self._tabs:
            entry = self._tabs[self._active]
            module = entry.get("module")
            hooks = entry.get("hooks")
            quit_fn = (getattr(hooks, "on_quit", None)
                       or getattr(module, "on_quit", None))
            if quit_fn:
                try:
                    if quit_fn() is False:
                        return  # vetoed
                except Exception:
                    pass
            base_name = entry.get("base_name", entry.get("display_name", name))
            self.close_tab(self._active)
            self._cleanup_screen_modules(base_name)

        # 2. Import new screen
        scr = _HOST_INSTANCE.Project.getScreen(name)
        if scr is None:
            return
        module = _HOST_INSTANCE._import_screen(scr)
        hooks = _HOST_INSTANCE._import_hooks(scr)
        icon = _HOST_INSTANCE._load_tab_icon(scr)
        display = _HOST_INSTANCE._unique_display_name(name)

        # 3. Open new tab
        self.open_tab(display, module, hooks=hooks, icon=icon, base_name=name)

        # 4. Handle args via ArgHandler
        if args is not None and module and hasattr(module, "ArgHandler"):
            try:
                module.ArgHandler.handle(args)
            except Exception:
                pass

    def _cleanup_screen_modules(self, screen_name: str):
        """Remove screen-specific entries from sys.modules to allow clean re-import."""
        prefixes = (
            f"Screens.{screen_name}.",
            f"modules.{screen_name}.",
        )
        to_delete = [k for k in sys.modules if any(k.startswith(p) for p in prefixes)]
        for key in to_delete:
            del sys.modules[key]
        gc.collect()

    def _cleanup_all_modules(self):
        """Clean up all screen modules owned by this TabManager."""
        for entry in list(self._tabs.values()):
            base_name = entry.get("base_name", entry.get("display_name", ""))
            if base_name:
                self._cleanup_screen_modules(base_name)

    def open_tab(self, name: str, module, hooks=None, icon=None,
                 insert_idx: int = -1, base_name: str = None,
                 tab_id: int | None = None) -> int | None:
        """Open a new tab and build its screen UI.

        Args:
            name:       Display label shown on the tab button.
            module:     Imported screen module.
            hooks:      Optional hooks module from ``modules/<name>/m_<name>.py``.
            icon:       Optional ``PIL.ImageTk.PhotoImage``.
            insert_idx: 0-based insertion position; -1 appends.
            base_name:  Screen registry name (same as *name* if no suffix).
            tab_id:     Optional existing tab_id to reuse (for SplitView
                rebuilds that must preserve tab identity across pane
                destruction). When ``None`` a fresh ID is allocated.

        Returns:
            The tab's ``tab_id`` on success, ``None`` if a tab with this
            exact display name already exists in *this* pane (callers with
            the same label across panes are fine).
        """
        # Reject only if the same ``tab_id`` is already registered —
        # SplitView rebuilds call with an explicit ``tab_id`` and require
        # the call to succeed even when a tab with a matching display
        # label is in the pane (it shouldn't be, because the pane is
        # fresh, but defensive ID-based gating is safer).
        if tab_id is not None and tab_id in self._tabs:
            return None

        # For fresh-ID callers: suppress duplicate labels in the same pane
        # by focusing the existing tab instead of creating a visual clone.
        if tab_id is None:
            existing = self._id_for_display(name)
            if existing is not None:
                self.tab_bar.focus_tab(existing)
                return None
            tab_id = new_id()

        frame = Frame(self._content)
        frame.place(relx=0, rely=0, relwidth=1, relheight=1)

        # Let screens call set_tab_info(parent, ...) from inside setup()
        frame._vis_tab_id      = tab_id
        frame._vis_tab_manager = self

        self._tabs[tab_id] = {
            "tab_id":        tab_id,
            "display_name":  name,
            "frame":         frame,
            "module":        module,
            "hooks":         hooks,
            "icon":          icon,
            "base_name":     base_name if base_name is not None else name,
            "info":          "",
            "_info_trace":   None,   # (StringVar, trace_id) | None
        }

        if module and hasattr(module, "setup"):
            try:
                module.setup(frame)
            except Exception:
                pass

        self.tab_bar.open_tab(tab_id, name, icon=icon, insert_idx=insert_idx)
        return tab_id

    def close_tab(self, key, skip_on_quit: bool = False) -> bool:
        """Close the tab identified by *key* (tab_id or display label).

        Args:
            key:          Tab ID (int) or display label (str).
            skip_on_quit: If True, skip the on_quit hook (used when
                DetachedWindow has already checked it).
        """
        tab_id = self._resolve_id(key)
        if tab_id is None:
            return False

        entry = self._tabs[tab_id]

        # Call on_quit unless skipped (e.g. window close already checked)
        if not skip_on_quit:
            module = entry.get("module")
            hooks = entry.get("hooks")
            quit_fn = (getattr(hooks, "on_quit", None)
                       or getattr(module, "on_quit", None))
            if quit_fn:
                try:
                    if quit_fn() is False:
                        return False  # vetoed
                except Exception:
                    pass

        # Clean up StringVar trace if present
        trace_info = entry.get("_info_trace")
        if trace_info is not None:
            var, tid = trace_info
            try:
                var.trace_remove("write", tid)
            except Exception:
                pass

        if self._active == tab_id:
            self._deactivate(tab_id)
            self._active = None

        entry["frame"].destroy()
        del self._tabs[tab_id]
        self.tab_bar.close_tab(tab_id)
        return True

    def focus_tab(self, key) -> bool:
        """Focus the tab identified by *key* (tab_id or display label)."""
        tab_id = self._resolve_id(key)
        if tab_id is None:
            return False
        return self.tab_bar.focus_tab(tab_id)

    def has_tab(self, key) -> bool:
        """Return whether *key* identifies an open tab."""
        return self._resolve_id(key) is not None

    def force_refresh_tab(self, key) -> bool:
        """Close and reopen the identified tab at its current position, re-running ``setup``.

        Preserves the same ``tab_id`` across the refresh so external
        references (``_pane_parents`` look-ups, recorded focus IDs, etc.)
        remain valid.
        """
        tab_id = self._resolve_id(key)
        if tab_id is None:
            return False
        idx       = self.tab_bar.get_tab_idx(tab_id)
        entry     = self._tabs[tab_id]
        display   = entry["display_name"]
        module    = entry.get("module")
        hooks     = entry.get("hooks")
        icon      = entry.get("icon")
        base_name = entry.get("base_name", display)

        # Tear down without calling on_quit
        if not self.close_tab(tab_id, skip_on_quit=True):
            return False

        # Re-open reusing the original tab_id so any external reference to
        # this tab (e.g. focus tracking in SplitView) survives the refresh.
        new_tab_id = self.open_tab(display, module, hooks=hooks, icon=icon,
                                    insert_idx=idx, base_name=base_name,
                                    tab_id=tab_id)
        return new_tab_id is not None

    def set_tab_info(self, key, info) -> None:
        """Set or trace the characteristic info for the identified tab.

        ``info`` may be a plain ``str`` or a ``tkinter.StringVar``.
        Replaces any previously registered trace.
        """
        tab_id = self._resolve_id(key)
        if tab_id is None:
            return
        # Remove existing trace if any
        old = self._tabs[tab_id].get("_info_trace")
        if old is not None:
            old_var, old_tid = old
            try:
                old_var.trace_remove("write", old_tid)
            except Exception:
                pass
            self._tabs[tab_id]["_info_trace"] = None

        # Detect StringVar by duck-typing
        if hasattr(info, "trace_add") and callable(info.trace_add):
            var = info
            tid = var.trace_add("write",
                                lambda *_: self._update_tab_info(tab_id, var.get()))
            self._tabs[tab_id]["_info_trace"] = (var, tid)
            self._update_tab_info(tab_id, var.get())
        else:
            self._update_tab_info(tab_id, str(info))

    # ── Hook lookup ────────────────────────────────────────────────────────────

    def _get_hook(self, tab_id: int, hook_name: str):
        entry = self._tabs.get(tab_id, {})
        fn = getattr(entry.get("hooks"), hook_name, None)
        if fn is None:
            fn = getattr(entry.get("module"), hook_name, None)
        return fn

    # ── Internal ───────────────────────────────────────────────────────────────

    def _update_tab_info(self, tab_id: int, info: str):
        """Update the stored info string and propagate to tab label + callback."""
        if tab_id not in self._tabs:
            return
        self._tabs[tab_id]["info"] = info
        name = self._tabs[tab_id]["display_name"]
        # Update tab button text
        display = f"{name} \u2014 {info}" if info else name
        self.tab_bar.update_tab_label(tab_id, display)
        # Notify interested parties (Host, DetachedWindow)
        if self.on_tab_info_change:
            self.on_tab_info_change(tab_id, info)

    def _deactivate(self, tab_id: int):
        if tab_id not in self._tabs:
            return
        self._tabs[tab_id]["frame"].lower()
        fn = self._get_hook(tab_id, "on_unfocused")
        if fn:
            try:
                fn()
            except Exception:
                pass
        if self.on_tab_deactivate:
            self.on_tab_deactivate(tab_id)

    def _call_configure_menu(self, tab_id: int):
        """Call configure_menu on the active tab's hooks or module.

        Supports both new signature (tabmanager) and old signature (menubar)
        for backwards compatibility.
        """
        cfg = self._get_hook(tab_id, "configure_menu")
        if cfg is None:
            return
        try:
            sig = inspect.signature(cfg)
            params = list(sig.parameters.keys())
            if params and params[0] == "menubar":
                # Old signature — pass menubar directly for compat
                if self._menubar:
                    cfg(self._menubar)
            else:
                cfg(self)
        except Exception:
            pass

    def _on_focus_change(self, tab_id: int | None):
        prev = self._active
        if prev is not None and prev != tab_id:
            self._deactivate(prev)

        self._active = tab_id

        if tab_id is not None and tab_id in self._tabs:
            self._tabs[tab_id]["frame"].lift()
            fn = self._get_hook(tab_id, "on_focused")
            if fn:
                try:
                    fn()
                except Exception:
                    pass
            if self.on_tab_activate:
                self.on_tab_activate(tab_id, self._tabs[tab_id].get("module"))
        elif tab_id is None and self.on_tab_deactivate:
            self.on_tab_deactivate(None)

    def _on_close_request(self, tab_id: int):
        entry = self._tabs.get(tab_id)
        if entry is None:
            return
        fn = self._get_hook(tab_id, "has_unsaved")
        if fn:
            try:
                if fn():
                    from tkinter import messagebox
                    if not messagebox.askyesno(
                        "Close tab",
                        f'"{entry["display_name"]}" has unsaved changes.\nClose anyway?',
                    ):
                        return
            except Exception:
                pass
        self.close_tab(tab_id)

    def _on_popout_request(self, tab_id: int):
        if self.on_tab_popout:
            self.on_tab_popout(tab_id)

    def _on_refresh_request(self, tab_id: int):
        if self.on_tab_refresh:
            self.on_tab_refresh(tab_id)
        else:
            self.force_refresh_tab(tab_id)

    def _on_detach_request(self, tab_id: int):
        if self.on_tab_detach:
            self.on_tab_detach(tab_id)

    def _on_split_request(self, tab_id: int, direction: str, target_pane=None):
        if self.on_tab_split:
            self.on_tab_split(tab_id, direction, target_pane)

    def _on_merge_request(self, tab_id: int, source_bar: "TabBar",
                          insert_idx: int = -1):
        """A drag from *source_bar* was released over this bar at *insert_idx*."""
        source_mgr = source_bar.owner
        if source_mgr is None or source_mgr is self:
            return
        if not source_mgr.has_tab(tab_id):
            return
        entry     = source_mgr._tabs[tab_id]
        display   = entry["display_name"]
        module    = entry.get("module")
        hooks     = entry.get("hooks")
        icon      = entry.get("icon")
        base_name = entry.get("base_name", display)
        if not source_mgr.close_tab(tab_id, skip_on_quit=True):
            return
        self.open_tab(display, module, hooks=hooks, icon=icon,
                      insert_idx=insert_idx, base_name=base_name)
