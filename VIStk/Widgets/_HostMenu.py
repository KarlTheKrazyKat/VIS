from tkinter import Menu, Tk, Toplevel


class HostMenu:
    """A persistent ``tk.Menu`` attached to the Host window.

    The menubar has three ordered layers:

    1. **Built-in layer** — the "App" cascade (Close Window / Quit), always
       first, built automatically by :meth:`attach`.
    2. **Project layer** — app-wide cascades added once at Host startup via
       :meth:`set_project_items`.  They persist across all tab changes.
    3. **Screen layer** — cascades contributed by the active tab's
       ``configure_menu`` hook via :meth:`set_screen_items`.  All screen
       cascades are cleared automatically when the tab deactivates.

    ``set_screen_items`` **accumulates** — calling it more than once within a
    single ``configure_menu`` hook appends multiple cascades side by side.
    All are removed together by :meth:`clear_screen_items`.

    Usage::

        host_menu = HostMenu(host_window, quit_command=host.quit_host)
        host_menu.attach()

        # In Host.py, once at startup — project-wide items:
        host_menu.set_project_items([
            {"label": "File", "items": [
                {"label": "New",  "command": new_fn},
                {"separator": True},
                {"label": "Exit", "command": host.quit_host},
            ]},
        ], label="File")

        # From a screen's configure_menu() hook — screen-specific items:
        host_menu.set_screen_items([
            {"label": "Export PDF", "command": export_pdf},
            {"label": "Print",      "command": print_fn},
        ], label="Work Orders")

    Item spec format (list of dicts)::

        {"label": str, "command": callable}              # simple command
        {"label": str, "items": [<item spec>, ...]}      # cascade submenu
        {"separator": True}                              # separator

    Attributes:
        menubar (Menu): The underlying Tk Menu widget.
    """

    def __init__(self, parent: Tk | Toplevel, quit_command=None,
                 close_command=None):
        self.menubar = Menu(parent, tearoff=0)
        self._parent = parent
        self._quit_command = quit_command
        self._close_command = close_command
        self._project_labels: list[str] = []
        self._screen_labels: list[str] = []

    # ── Public API ─────────────────────────────────────────────────────────────

    def attach(self):
        """Configure the parent window to show this menu bar."""
        self._parent.config(menu=self.menubar)
        self._build_base()

    def set_project_items(self, items: list[dict], label: str = "Project"):
        """Add one cascade to the project layer.

        May be called multiple times to add multiple project-layer cascades in
        order.  Project cascades persist across all tab changes and are only
        removed by :meth:`clear_project_items`.

        Args:
            items: List of item spec dicts (see class docstring).
            label: Cascade label shown in the menu bar.
        """
        if not items:
            return
        cascade = Menu(self.menubar, tearoff=0)
        self._populate(cascade, items)
        self.menubar.add_cascade(label=label, menu=cascade)
        self._project_labels.append(label)

    def clear_project_items(self):
        """Remove all project-layer cascades.

        Intended for teardown; not normally called during regular use.
        """
        for label in self._project_labels:
            try:
                self.menubar.delete(label)
            except Exception:
                pass
        self._project_labels.clear()

    def set_screen_items(self, items: list[dict], label: str = "Screen"):
        """Add one cascade to the screen layer (accumulates).

        Calling this multiple times within a single ``configure_menu`` hook
        appends multiple cascades side by side — all are cleared together when
        the tab deactivates.

        Args:
            items: List of item spec dicts (see class docstring).
            label: Cascade label shown in the menu bar.
        """
        if not items:
            return
        cascade = Menu(self.menubar, tearoff=0)
        self._populate(cascade, items)
        self.menubar.add_cascade(label=label, menu=cascade)
        self._screen_labels.append(label)

    def clear_screen_items(self):
        """Remove all accumulated screen cascades."""
        for label in self._screen_labels:
            try:
                self.menubar.delete(label)
            except Exception:
                pass
        self._screen_labels.clear()

    # ── Internal ───────────────────────────────────────────────────────────────

    def _build_base(self):
        app_menu = Menu(self.menubar, tearoff=0)
        if self._close_command:
            app_menu.add_command(label="Close Window", command=self._close_command)
        if self._quit_command:
            if self._close_command:
                app_menu.add_separator()
            app_menu.add_command(label="Quit", command=self._quit_command)
        elif not self._close_command:
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
