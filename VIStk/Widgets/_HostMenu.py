from tkinter import Menu, Tk, Toplevel


class HostMenu:
    """A persistent ``tk.Menu`` attached to the Host window.

    Base items (e.g. Quit) are always present.  When a tab activates its
    screen calls ``set_screen_items(items)`` to contribute screen-specific
    cascades or commands; those are cleared automatically when the tab
    deactivates.

    Usage::

        host_menu = HostMenu(host_window)
        host_menu.attach()

        # From a screen's configure_menu() hook:
        host_menu.set_screen_items([
            {"label": "File", "items": [
                {"label": "Open",  "command": open_fn},
                {"label": "Close", "command": close_fn},
            ]},
        ])

    Item spec format (list of dicts)::

        {"label": str, "command": callable}              # simple command
        {"label": str, "items": [<item spec>, ...]}      # cascade submenu
        {"separator": True}                              # separator

    Attributes:
        menubar (Menu): The underlying Tk Menu widget.
    """

    def __init__(self, parent: Tk | Toplevel, quit_command=None):
        self.menubar = Menu(parent, tearoff=0)
        self._parent = parent
        self._quit_command = quit_command
        self._screen_cascade: Menu | None = None
        self._screen_label: str | None = None

    # ── Public API ─────────────────────────────────────────────────────────────

    def attach(self):
        """Configure the parent window to show this menu bar."""
        self._parent.config(menu=self.menubar)
        self._build_base()

    def set_screen_items(self, items: list[dict], label: str = "Screen"):
        """Replace the screen-contributed section with *items*.

        Args:
            items: List of item spec dicts (see class docstring).
            label: Cascade label shown in the menu bar for screen items.
        """
        self.clear_screen_items()
        if not items:
            return
        cascade = Menu(self.menubar, tearoff=0)
        self._populate(cascade, items)
        self.menubar.add_cascade(label=label, menu=cascade)
        self._screen_cascade = cascade
        self._screen_label = label

    def clear_screen_items(self):
        """Remove the screen-contributed menu section."""
        if self._screen_label is not None:
            try:
                self.menubar.delete(self._screen_label)
            except Exception:
                pass
            self._screen_cascade = None
            self._screen_label = None

    # ── Internal ───────────────────────────────────────────────────────────────

    def _build_base(self):
        app_menu = Menu(self.menubar, tearoff=0)
        if self._quit_command:
            app_menu.add_command(label="Quit", command=self._quit_command)
        else:
            app_menu.add_command(label="Quit", command=self._parent.destroy)
        self.menubar.add_cascade(label="App", menu=app_menu)

    def _populate(self, menu: Menu, items: list[dict]):
        for item in items:
            if item.get("separator"):
                menu.add_separator()
            elif "items" in item:
                sub = Menu(menu, tearoff=0)
                self._populate(sub, item["items"])
                menu.add_cascade(label=item.get("label", ""), menu=sub)
            else:
                menu.add_command(
                    label=item.get("label", ""),
                    command=item.get("command"),
                )
