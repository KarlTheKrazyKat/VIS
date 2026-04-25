from tkinter import Menu, Tk, Toplevel, TclError


class HostMenu:
    """A persistent ``tk.Menu`` attached to the Host window.

    The menubar has two ordered layers:

    1. **Project layer** — app-wide cascades added once at Host startup via
       :meth:`set_project_items`.  They persist across all tab changes.
    2. **Screen layer** — cascades contributed by the active tab's
       ``configure_menu`` hook via :meth:`set_screen_items`.  All screen
       cascades are cleared automatically when the tab deactivates.

    ``set_screen_items`` **accumulates** — calling it more than once within a
    single ``configure_menu`` hook appends multiple cascades side by side.
    All are removed together by :meth:`clear_screen_items`.

    A third, optional layer is the **shared layer** — persistent cascades
    built once at startup via :meth:`build_shared_menu` whose individual leaf
    items can be patched per-tab with :meth:`apply_overrides` and restored to
    their build-time defaults with :meth:`reset_overrides`.

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
        self._replaced_shared: set[str] = set()
        self._shared_menus: dict[str, Menu] = {}
        self._shared_defaults: dict[str, dict[str, dict]] = {}
        self._hidden_shared: list[tuple[str, int, Menu]] = []

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

    def add_project_command(self, label: str, command) -> None:
        """Add one leaf command directly to the menubar (project layer).

        Unlike :meth:`set_project_items` which adds a cascade (a dropdown),
        this adds a single clickable menubar entry whose label *is* the
        action — e.g. a top-level ``Help`` button.  Persists across all
        tab changes; only removed by :meth:`clear_project_items`.

        May be called multiple times to add more than one top-level
        command, side by side, in call order.

        Args:
            label:   Top-level label shown on the menubar.
            command: Zero-arg callable invoked when the user clicks.
        """
        self.menubar.add_command(label=label, command=command)
        self._project_labels.append(label)

    def clear_project_items(self):
        """Remove all project-layer cascades.

        Intended for teardown; not normally called during regular use.
        """
        for label in self._project_labels:
            try:
                self.menubar.delete(label)
            except TclError:
                pass
        self._project_labels.clear()

    def set_screen_items(self, items: list[dict], label: str = "Screen"):
        """Add one cascade to the screen layer (accumulates).

        If *label* matches an existing shared-menu cascade, the shared
        cascade is temporarily replaced in-place so the menu bar keeps
        the same ordering.  On :meth:`clear_screen_items` the shared
        cascade is restored automatically.

        Args:
            items: List of item spec dicts (see class docstring).
            label: Cascade label shown in the menu bar.
        """
        if not items:
            return
        cascade = Menu(self.menubar, tearoff=0)
        self._populate(cascade, items)

        # If a shared cascade with this label exists, replace it in-place
        if label in self._shared_menus:
            try:
                idx = self.menubar.index(label)
                old_menu = self._shared_menus[label]
                self._hidden_shared.append((label, idx, old_menu))
                self.menubar.entryconfigure(idx, menu=cascade)
                self._replaced_shared.add(label)
                self._screen_labels.append(label)
                return
            except TclError:
                pass

        self.menubar.add_cascade(label=label, menu=cascade)
        self._screen_labels.append(label)

    def clear_screen_items(self):
        """Remove all accumulated screen cascades and restore shared ones."""
        for label in reversed(self._screen_labels):
            if label in self._replaced_shared:
                continue
            try:
                self.menubar.delete(label)
            except TclError:
                pass
        self._screen_labels.clear()
        self._replaced_shared.clear()
        # Restore hidden shared cascades
        for label, idx, old_menu in self._hidden_shared:
            try:
                self.menubar.entryconfigure(idx, menu=old_menu)
            except TclError:
                pass
        self._hidden_shared.clear()

    def build_shared_menu(self, structure: dict):
        """Build the persistent shared menu from a structure dict.

        Called once at Host startup. Creates one cascade per top-level key
        (e.g. "File", "Edit") and adds them to the menubar as project-layer
        items. Stores Menu widget references in _shared_menus and default
        command/state values for every leaf item in _shared_defaults so that
        reset_overrides() can restore them.

        structure format::

            {
                "File": [
                    {"label": "Open...", "command": None, "state": "disabled"},
                    {"separator": True},
                    {"label": "Exit", "command": exit_fn},
                    {"label": "New", "items": [...]},  # submenu — not patchable
                ],
                "Edit": [...],
            }

        Only top-level items (direct children of a cascade) are tracked for
        override/reset. Nested submenu items are static.

        Args:
            structure: Mapping of cascade label to list of item spec dicts.
                       Each item spec may include a ``state`` key
                       (``"normal"`` or ``"disabled"``); defaults to
                       ``"normal"`` when omitted.
        """
        self._shared_structure = structure
        for label, items in structure.items():
            cascade = Menu(self.menubar, tearoff=0)
            defaults: dict[str, dict] = {}
            for item in items:
                if item.get("separator"):
                    cascade.add_separator()
                elif "items" in item:
                    sub = Menu(cascade, tearoff=0)
                    self._populate(sub, item["items"])
                    cascade.add_cascade(label=item.get("label", ""), menu=sub)
                else:
                    kw = {
                        "label":   item.get("label", ""),
                        "command": item.get("command"),
                        "state":   item.get("state", "normal"),
                    }
                    cascade.add_command(**kw)
                    # Record defaults so reset_overrides can restore them
                    defaults[kw["label"]] = {
                        "command": kw["command"],
                        "state":   kw["state"],
                    }
            self.menubar.add_cascade(label=label, menu=cascade)
            self._project_labels.append(label)
            self._shared_menus[label] = cascade
            self._shared_defaults[label] = defaults

    def apply_overrides(self, overrides: dict):
        """Patch shared menu items with screen-specific commands/states.

        overrides format::

            {
                "File": {
                    "Open...": {"command": fn, "state": "normal"},
                    "Save":    {"command": fn, "state": "normal"},
                },
            }

        Unknown cascade labels or item labels are silently ignored.

        Args:
            overrides: Mapping of cascade label to a mapping of item label
                       to ``entryconfig`` keyword arguments.
        """
        for cascade_label, items in overrides.items():
            cascade = self._shared_menus.get(cascade_label)
            if cascade is None:
                continue
            for item_label, opts in items.items():
                try:
                    cascade.entryconfig(item_label, **opts)
                except TclError:
                    pass

    def reset_overrides(self):
        """Restore all shared menu items to their build-time defaults.

        Called on tab deactivate and before apply_overrides on tab activate.
        """
        for cascade_label, defaults in self._shared_defaults.items():
            cascade = self._shared_menus.get(cascade_label)
            if cascade is None:
                continue
            for item_label, opts in defaults.items():
                try:
                    cascade.entryconfig(item_label, **opts)
                except TclError:
                    pass

    # ── Default snapshot ──────────────────────────────────────────────────────

    def save_defaults(self):
        """Snapshot the current menubar state (called once after setup)."""
        idx = self.menubar.index("end")
        self._default_end = idx if idx is not None else 0

    def restore_defaults(self):
        """Reset the menubar to the snapshot taken by save_defaults().

        Removes any cascades added after the snapshot.
        """
        if not hasattr(self, "_default_end") or self._default_end is None:
            return
        current = self.menubar.index("end")
        if current is not None and self._default_end is not None:
            for i in range(current, self._default_end, -1):
                try:
                    self.menubar.delete(i)
                except TclError:
                    pass

    # ── Internal ───────────────────────────────────────────────────────────────

    def _build_base(self):
        pass

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