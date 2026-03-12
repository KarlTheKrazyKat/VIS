from __future__ import annotations

from tkinter import Frame

from VIStk.Widgets._TabBar import TabBar, _BG_BAR


class TabManager(Frame):
    """Manages the tabbed screen area of the Host window.

    ``TabManager`` is a ``Frame`` that fills the Host window.  It owns two
    child frames:

    * ``tab_bar`` — a :class:`~VIStk.Widgets._TabBar.TabBar` widget packed
      along the top edge, showing one button per open screen.
    * The *content frame* (internal) — fills the remaining space; each
      screen's ``setup(frame)`` receives a ``Frame`` placed inside here.

    Screen modules are imported externally (by the Host) and passed to
    :meth:`open_tab`.  ``TabManager`` calls ``module.setup(frame)``,
    ``module.on_activate()``, and ``module.on_deactivate()`` at the
    appropriate times.

    Callbacks let the Host react to tab lifecycle events without coupling
    ``TabManager`` to Host-specific objects like ``HostMenu``::

        manager.on_tab_activate   = lambda name, mod: ...
        manager.on_tab_deactivate = lambda name: ...

    Attributes:
        tab_bar (TabBar): The tab strip widget (publicly accessible).
        on_tab_activate (callable | None): Called with ``(name, module)``
            when a tab gains focus.
        on_tab_deactivate (callable | None): Called with ``(name)``
            when a tab loses focus; also called with ``None`` when all tabs
            are closed.
    """

    def __init__(self, parent, **kwargs):
        kwargs.setdefault("bg", _BG_BAR)
        super().__init__(parent, **kwargs)

        self._tabs: dict[str, dict] = {}
        """name → {"frame": Frame, "module": module | None}"""
        self._active: str | None = None

        # Callbacks wired by the Host
        self.on_tab_activate = None   # callable(name: str, module)
        self.on_tab_deactivate = None  # callable(name: str | None)

        # ── Widgets ────────────────────────────────────────────────────────────
        self.tab_bar = TabBar(self)
        self.tab_bar.pack(side="top", fill="x")

        self._content = Frame(self)
        self._content.pack(side="top", fill="both", expand=True)

        # Wire TabBar callbacks back to this manager
        self.tab_bar.on_focus_change = self._on_focus_change
        self.tab_bar.on_tab_close = self._on_close_request

    # ── Public API ─────────────────────────────────────────────────────────────

    @property
    def active(self) -> str | None:
        """Name of the currently active tab, or ``None``."""
        return self._active

    def open_tab(self, name: str, module, icon=None) -> bool:
        """Open a new tab for *name* and build its screen UI.

        If a tab with *name* already exists it is focused instead and no
        new frame is created.

        Args:
            name:   Screen name used as the tab label.
            module: Imported screen module.  ``module.setup(frame)`` is called
                    with a fresh ``Frame`` if the hook is present.
            icon:   Optional ``PIL.ImageTk.PhotoImage`` shown to the left of
                    the tab label.  The reference is kept alive in the tab dict.

        Returns:
            ``True`` if a new tab was created, ``False`` if it already existed.
        """
        if name in self._tabs:
            self.tab_bar.focus_tab(name)
            return False

        frame = Frame(self._content)
        frame.place(relx=0, rely=0, relwidth=1, relheight=1)

        if module and hasattr(module, "setup"):
            try:
                module.setup(frame)
            except Exception:
                pass

        self._tabs[name] = {"frame": frame, "module": module, "icon": icon}
        # open_tab → internally calls focus_tab → triggers _on_focus_change
        self.tab_bar.open_tab(name, icon=icon)
        return True

    def close_tab(self, name: str) -> bool:
        """Close the named tab.

        Calls ``on_deactivate`` on the module if the tab was active, then
        destroys the frame and removes the tab button.

        Returns:
            ``True`` if the tab was found and removed, ``False`` otherwise.
        """
        if name not in self._tabs:
            return False

        if self._active == name:
            self._deactivate(name)
            self._active = None

        self._tabs[name]["frame"].destroy()
        del self._tabs[name]
        # TabBar.close_tab handles refocusing any remaining tab
        self.tab_bar.close_tab(name)
        return True

    def focus_tab(self, name: str) -> bool:
        """Focus the named tab.

        Returns:
            ``True`` if the tab exists and was focused, ``False`` otherwise.
        """
        return self.tab_bar.focus_tab(name)

    def has_tab(self, name: str) -> bool:
        """Return whether a tab with *name* is currently open."""
        return name in self._tabs

    # ── Internal ───────────────────────────────────────────────────────────────

    def _deactivate(self, name: str):
        """Run deactivation hooks for *name* without removing the tab."""
        if name not in self._tabs:
            return
        self._tabs[name]["frame"].lower()
        mod = self._tabs[name].get("module")
        if mod and hasattr(mod, "on_deactivate"):
            try:
                mod.on_deactivate()
            except Exception:
                pass
        if self.on_tab_deactivate:
            self.on_tab_deactivate(name)

    def _on_focus_change(self, name: str | None):
        """Invoked by ``TabBar`` when the active tab changes."""
        prev = self._active

        # Deactivate the previously active tab
        if prev and prev != name:
            self._deactivate(prev)

        self._active = name

        if name and name in self._tabs:
            self._tabs[name]["frame"].lift()
            mod = self._tabs[name].get("module")
            if mod:
                if hasattr(mod, "on_activate"):
                    try:
                        mod.on_activate()
                    except Exception:
                        pass
                if self.on_tab_activate:
                    self.on_tab_activate(name, mod)
        elif name is None and self.on_tab_deactivate:
            # All tabs closed
            self.on_tab_deactivate(None)

    def _on_close_request(self, name: str):
        """Invoked by ``TabBar``'s close button."""
        self.close_tab(name)
