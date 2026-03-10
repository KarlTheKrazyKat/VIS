from tkinter import ttk
from tkinter import *


class TabBar(ttk.Frame):
    """A row of clickable tabs displayed at the top of the Host window.

    Each tab represents an open screen.  Clicking a tab focuses it;
    the close button on each tab closes it.

    Attributes:
        active (str | None): Name of the currently focused tab.
        on_focus_change (callable | None): Optional callback invoked with
            ``(name: str)`` whenever the active tab changes.
        on_tab_close (callable | None): Optional callback invoked with
            ``(name: str)`` when a tab's close button is pressed.
    """

    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self._tabs: dict[str, dict] = {}
        """name → {"button": Button, "close": Button}"""
        self.active: str | None = None
        self.on_focus_change = None
        self.on_tab_close = None

    # ── Public API ─────────────────────────────────────────────────────────────

    def open_tab(self, name: str) -> bool:
        """Add a tab for *name*.  Does nothing if the tab already exists.

        Returns:
            True if a new tab was created, False if it already existed.
        """
        if name in self._tabs:
            return False

        btn = Button(
            self,
            text=name,
            relief="flat",
            command=lambda n=name: self.focus_tab(n),
        )
        btn.pack(side="left", padx=(2, 0), pady=2)

        close_btn = Button(
            self,
            text="✕",
            relief="flat",
            width=2,
            command=lambda n=name: self._close(n),
        )
        close_btn.pack(side="left", padx=(0, 4), pady=2)

        self._tabs[name] = {"button": btn, "close": close_btn}
        self.focus_tab(name)
        return True

    def close_tab(self, name: str) -> bool:
        """Remove the tab for *name*.

        Returns:
            True if removed, False if not found.
        """
        if name not in self._tabs:
            return False
        self._tabs[name]["button"].destroy()
        self._tabs[name]["close"].destroy()
        del self._tabs[name]
        if self.active == name:
            self.active = None
            # Focus the last remaining tab if any
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

    # ── Internal ───────────────────────────────────────────────────────────────

    def _close(self, name: str):
        if self.on_tab_close:
            self.on_tab_close(name)
        self.close_tab(name)

    def _update_styles(self):
        for name, widgets in self._tabs.items():
            if name == self.active:
                widgets["button"].config(relief="sunken")
            else:
                widgets["button"].config(relief="flat")
