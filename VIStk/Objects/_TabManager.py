from __future__ import annotations

from tkinter import Frame

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
    mgr  = getattr(frame, "_vis_tab_manager", None)
    name = getattr(frame, "_vis_tab_name",    None)
    if mgr is not None and name is not None:
        mgr.set_tab_info(name, info)


class TabManager(Frame):
    """Manages the tabbed screen area of the Host window.

    ``TabManager`` is a ``Frame`` that fills the Host window.  It owns two
    child frames:

    * ``tab_bar`` — a :class:`~VIStk.Widgets._TabBar.TabBar` packed along
      the top edge.
    * The *content frame* (internal) — fills the remaining space.

    Hook lookup priority: if ``modules/<screen>/m_<screen>.py`` exists,
    ``TabManager`` checks it first for ``on_focused``, ``on_unfocused``, and
    ``configure_menu``.  The screen module is used as a fallback.

    Callbacks::

        manager.on_tab_activate    = lambda name, mod: ...
        manager.on_tab_deactivate  = lambda name: ...
        manager.on_tab_popout      = lambda name: ...
        manager.on_tab_detach      = lambda name: ...
        manager.on_tab_refresh     = lambda name: ...
        manager.on_tab_info_change = lambda name, info: ...

    Attributes:
        tab_bar            (TabBar)
        on_tab_activate    (callable | None) ``(name, module)``
        on_tab_deactivate  (callable | None) ``(name | None)``
        on_tab_popout      (callable | None) ``(name)``
        on_tab_detach      (callable | None) ``(name)``
        on_tab_refresh     (callable | None) ``(name)``
        on_tab_info_change (callable | None) ``(name, info)``
        on_tab_split       (callable | None) ``(name, direction)``
    """

    def __init__(self, parent, **kwargs):
        kwargs.setdefault("bg", _BG_BAR)
        super().__init__(parent, **kwargs)

        self._tabs: dict[str, dict] = {}
        """name → {frame, module, hooks, icon, base_name, info, _info_trace}"""
        self._active: str | None = None

        self.on_tab_activate   = None
        self.on_tab_deactivate = None
        self.on_tab_popout     = None
        self.on_tab_detach     = None
        self.on_tab_refresh    = None
        self.on_tab_info_change = None
        self.on_tab_split      = None

        self.tab_bar = TabBar(self)
        self.tab_bar.pack(side="top", fill="x")
        self.tab_bar.owner = self

        self._content = Frame(self)
        self._content.pack(side="top", fill="both", expand=True)

        self.tab_bar.on_focus_change = self._on_focus_change
        self.tab_bar.on_tab_close    = self._on_close_request
        self.tab_bar.on_tab_popout   = self._on_popout_request
        self.tab_bar.on_tab_refresh  = self._on_refresh_request
        self.tab_bar.on_drag_detach  = self._on_detach_request
        self.tab_bar.on_drag_merge   = self._on_merge_request
        self.tab_bar.on_tab_split    = self._on_split_request

    # ── Public API ─────────────────────────────────────────────────────────────

    @property
    def active(self) -> str | None:
        return self._active

    def open_tab(self, name: str, module, hooks=None, icon=None,
                 insert_idx: int = -1, base_name: str = None) -> bool:
        """Open a new tab for *name* and build its screen UI.

        Args:
            name:       Display name / tab label.
            module:     Imported screen module.
            hooks:      Optional hooks module from ``modules/<name>/m_<name>.py``.
            icon:       Optional ``PIL.ImageTk.PhotoImage``.
            insert_idx: 0-based insertion position; -1 appends.
            base_name:  Screen registry name (same as *name* if no suffix).

        Returns:
            ``True`` if a new tab was created, ``False`` if it already existed.
        """
        if name in self._tabs:
            self.tab_bar.focus_tab(name)
            return False

        frame = Frame(self._content)
        frame.place(relx=0, rely=0, relwidth=1, relheight=1)

        # Let screens call set_tab_info(parent, ...) from inside setup()
        frame._vis_tab_name    = name
        frame._vis_tab_manager = self

        if module and hasattr(module, "setup"):
            try:
                module.setup(frame)
            except Exception:
                pass

        self._tabs[name] = {
            "frame":      frame,
            "module":     module,
            "hooks":      hooks,
            "icon":       icon,
            "base_name":  base_name if base_name is not None else name,
            "info":       "",
            "_info_trace": None,   # (StringVar, trace_id) | None
        }
        self.tab_bar.open_tab(name, icon=icon, insert_idx=insert_idx)
        return True

    def close_tab(self, name: str) -> bool:
        """Close the named tab, running ``on_unfocused`` first."""
        if name not in self._tabs:
            return False

        # Clean up StringVar trace if present
        trace_info = self._tabs[name].get("_info_trace")
        if trace_info is not None:
            var, tid = trace_info
            try:
                var.trace_remove("write", tid)
            except Exception:
                pass

        if self._active == name:
            self._deactivate(name)
            self._active = None

        self._tabs[name]["frame"].destroy()
        del self._tabs[name]
        self.tab_bar.close_tab(name)
        return True

    def focus_tab(self, name: str) -> bool:
        return self.tab_bar.focus_tab(name)

    def has_tab(self, name: str) -> bool:
        return name in self._tabs

    def force_refresh_tab(self, name: str) -> bool:
        """Close and reopen *name* at its current position, re-running ``setup``."""
        if name not in self._tabs:
            return False
        idx       = self.tab_bar.get_tab_idx(name)
        entry     = self._tabs[name]
        module    = entry.get("module")
        hooks     = entry.get("hooks")
        icon      = entry.get("icon")
        base_name = entry.get("base_name", name)
        self.close_tab(name)
        self.open_tab(name, module, hooks=hooks, icon=icon,
                      insert_idx=idx, base_name=base_name)
        return True

    def set_tab_info(self, name: str, info) -> None:
        """Set or trace the characteristic info for tab *name*.

        ``info`` may be a plain ``str`` or a ``tkinter.StringVar``.
        Replaces any previously registered trace.
        """
        if name not in self._tabs:
            return
        # Remove existing trace if any
        old = self._tabs[name].get("_info_trace")
        if old is not None:
            old_var, old_tid = old
            try:
                old_var.trace_remove("write", old_tid)
            except Exception:
                pass
            self._tabs[name]["_info_trace"] = None

        # Detect StringVar by duck-typing
        if hasattr(info, "trace_add") and callable(info.trace_add):
            var = info
            tid = var.trace_add("write",
                                lambda *_: self._update_tab_info(name, var.get()))
            self._tabs[name]["_info_trace"] = (var, tid)
            self._update_tab_info(name, var.get())
        else:
            self._update_tab_info(name, str(info))

    # ── Hook lookup ────────────────────────────────────────────────────────────

    def _get_hook(self, name: str, hook_name: str):
        entry = self._tabs.get(name, {})
        fn = getattr(entry.get("hooks"), hook_name, None)
        if fn is None:
            fn = getattr(entry.get("module"), hook_name, None)
        return fn

    # ── Internal ───────────────────────────────────────────────────────────────

    def _update_tab_info(self, name: str, info: str):
        """Update the stored info string and propagate to tab label + callback."""
        if name not in self._tabs:
            return
        self._tabs[name]["info"] = info
        # Update tab button text
        display = f"{name} \u2014 {info}" if info else name
        self.tab_bar.update_tab_label(name, display)
        # Notify interested parties (Host, DetachedWindow)
        if self.on_tab_info_change:
            self.on_tab_info_change(name, info)

    def _deactivate(self, name: str):
        if name not in self._tabs:
            return
        self._tabs[name]["frame"].lower()
        fn = self._get_hook(name, "on_unfocused")
        if fn:
            try:
                fn()
            except Exception:
                pass
        if self.on_tab_deactivate:
            self.on_tab_deactivate(name)

    def _on_focus_change(self, name: str | None):
        prev = self._active
        if prev and prev != name:
            self._deactivate(prev)

        self._active = name

        if name and name in self._tabs:
            self._tabs[name]["frame"].lift()
            fn = self._get_hook(name, "on_focused")
            if fn:
                try:
                    fn()
                except Exception:
                    pass
            if self.on_tab_activate:
                self.on_tab_activate(name, self._tabs[name].get("module"))
        elif name is None and self.on_tab_deactivate:
            self.on_tab_deactivate(None)

    def _on_close_request(self, name: str):
        self.close_tab(name)

    def _on_popout_request(self, name: str):
        if self.on_tab_popout:
            self.on_tab_popout(name)

    def _on_refresh_request(self, name: str):
        if self.on_tab_refresh:
            self.on_tab_refresh(name)
        else:
            self.force_refresh_tab(name)

    def _on_detach_request(self, name: str):
        if self.on_tab_detach:
            self.on_tab_detach(name)

    def _on_split_request(self, name: str, direction: str):
        if self.on_tab_split:
            self.on_tab_split(name, direction)

    def _on_merge_request(self, name: str, source_bar: "TabBar", insert_idx: int = -1):
        """A drag from *source_bar* was released over this bar at *insert_idx*."""
        source_mgr = source_bar.owner
        if source_mgr is None or source_mgr is self:
            return
        if not source_mgr.has_tab(name):
            return
        entry     = source_mgr._tabs[name]
        module    = entry.get("module")
        hooks     = entry.get("hooks")
        icon      = entry.get("icon")
        base_name = entry.get("base_name", name)
        source_mgr.close_tab(name)
        self.open_tab(name, module, hooks=hooks, icon=icon,
                      insert_idx=insert_idx, base_name=base_name)
