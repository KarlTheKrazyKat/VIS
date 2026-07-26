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

    On Windows, top-level entries added with :meth:`add_project_command` can
    additionally carry a **native bitmap** (pass a ``PIL.Image.Image``) and be
    **right-aligned** on the real menubar strip (``align="right"``) — see
    ``Widgets/_MenuNative.py``.  Tk rebuilds the native menu on every
    mutation, dropping those patches, so every menubar-mutating method here
    ends by scheduling a coalesced :meth:`refresh_native`.

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
        # Native (Windows) menubar patches: label -> {right, image, hbitmap}.
        # Re-applied after every Tk menu mutation (Tk rebuilds the native
        # menu and drops out-of-band patches).
        self._native_patches: dict[str, dict] = {}
        self._image_refs: list = []          # keep PhotoImages alive (Tk GC)
        self._native_refresh_pending = False
        parent.bind("<Map>", self._on_map, add="+")
        parent.bind("<Destroy>", self._on_destroy, add="+")

    @property
    def window(self) -> Tk | Toplevel:
        """The window this menu bar is attached to."""
        return self._parent

    # ── Public API ─────────────────────────────────────────────────────────────

    def attach(self):
        """Configure the parent window to show this menu bar."""
        self._parent.config(menu=self.menubar)
        self._build_base()
        self._schedule_native_refresh()

    def detach(self):
        """Remove this menu bar from the parent window without destroying it.

        Counterpart to :meth:`attach`.  The underlying ``Menu`` widget and
        all its cascades / state stay alive, so screen code that calls
        ``set_screen_items`` / ``restore_defaults`` continues to work — the
        mutations just aren't visible on the window.

        Used by chromeless ``DetachedWindow`` instances whose active screen
        opts out of the host menubar via ``host_menubar=False`` in
        ``project.json``.
        """
        try:
            self._parent.config(menu="")
        except Exception:
            pass

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
        first_right = self._first_right_index()
        if first_right is None:
            self.menubar.add_cascade(label=label, menu=cascade)
        else:
            # A right-aligned native entry exists — MFT_RIGHTJUSTIFY drags
            # every subsequent item right with it, so insert before it.
            self.menubar.insert_cascade(first_right, label=label,
                                        menu=cascade)
        self._project_labels.append(label)
        self._schedule_native_refresh()

    def add_project_command(self, label: str, command, image=None,
                            compound=None, align=None) -> None:
        """Add one leaf command directly to the menubar (project layer).

        Unlike :meth:`set_project_items` which adds a cascade (a dropdown),
        this adds a single clickable menubar entry whose label *is* the
        action — e.g. a top-level ``Help`` button.  Persists across all
        tab changes; only removed by :meth:`clear_project_items`.

        May be called multiple times to add more than one top-level
        command, side by side, in call order.

        Args:
            label:    Top-level label shown on the menubar.
            command:  Zero-arg callable invoked when the user clicks.
            image:    Optional image shown with the label — either a Tk
                      ``PhotoImage`` or a ``PIL.Image.Image``.  NOTE: the
                      menubar is a native OS menu — Tk ignores the option on
                      the Windows top-level strip, but a **PIL** image is
                      rendered there natively (patched onto the real menu as
                      a premultiplied-alpha bitmap; see
                      ``Widgets/_MenuNative.py``).  Off-Windows a PIL image
                      falls back to ``ImageTk.PhotoImage`` (the reference is
                      kept alive on this object) — on X11 the Tk-drawn
                      menubar renders it.  For a caller-supplied
                      ``PhotoImage``, keep your own reference alive to avoid
                      GC.
            compound: Icon/text arrangement when *image* is set (default
                      ``"left"``).  Ignored on the native (Windows) bitmap
                      path.
            align:    ``"right"`` right-justifies the entry on the native
                      Windows menubar (the entry — and any entry after it —
                      hugs the right edge of the bar).  Works with or
                      without an image; ignored off-Windows.

        The entry can be relabelled later with
        ``host_menu.menubar.entryconfigure(<current label>, label=...,
        image=...)``; to swap a native bitmap without touching the Tk entry
        use :meth:`set_native_image`.
        """
        from VIStk.Widgets import _MenuNative

        kw = {"label": label, "command": command}
        native = None    # pending {right, image, hbitmap} patch, if any
        if image is not None:
            pil_image = None
            try:
                from PIL import Image
                if isinstance(image, Image.Image):
                    pil_image = image
            except ImportError:
                pass
            if pil_image is not None:
                if _MenuNative.available():
                    # Don't hand the image to Tk — patch the native menu.
                    native = {"right": align == "right",
                              "image": pil_image, "hbitmap": None}
                else:
                    # Legacy path: Tk-drawn menubars (X11) render the image.
                    from PIL import ImageTk
                    photo = ImageTk.PhotoImage(pil_image)
                    self._image_refs.append(photo)
                    kw["image"] = photo
                    kw["compound"] = compound or "left"
            else:
                kw["image"] = image
                kw["compound"] = compound or "left"
        if align == "right" and native is None and _MenuNative.available():
            native = {"right": True, "image": None, "hbitmap": None}

        if native is not None and native["right"]:
            # Right-aligned entries append at the end (rightmost).
            self.menubar.add_command(**kw)
        else:
            first_right = self._first_right_index()
            if first_right is None:
                self.menubar.add_command(**kw)
            else:
                # Keep left-side entries left of the right-aligned block.
                self.menubar.insert_command(first_right, **kw)
        self._project_labels.append(label)
        if native is not None:
            self._native_patches[label] = native
        self._schedule_native_refresh()

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
        self._schedule_native_refresh()

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
                self._schedule_native_refresh()
                return
            except TclError:
                pass

        first_right = self._first_right_index()
        if first_right is None:
            self.menubar.add_cascade(label=label, menu=cascade)
        else:
            # Keep screen cascades left of the right-aligned native block
            # (MFT_RIGHTJUSTIFY drags everything after it to the right).
            self.menubar.insert_cascade(first_right, label=label,
                                        menu=cascade)
        self._screen_labels.append(label)
        self._schedule_native_refresh()

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
        self._schedule_native_refresh()

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
            first_right = self._first_right_index()
            if first_right is None:
                self.menubar.add_cascade(label=label, menu=cascade)
            else:
                self.menubar.insert_cascade(first_right, label=label,
                                            menu=cascade)
            self._project_labels.append(label)
            self._shared_menus[label] = cascade
            self._shared_defaults[label] = defaults
        self._schedule_native_refresh()

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
        self._schedule_native_refresh()

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
        self._schedule_native_refresh()

    # ── Default snapshot ──────────────────────────────────────────────────────

    def save_defaults(self):
        """Snapshot the current menubar state (called once after setup)."""
        idx = self.menubar.index("end")
        self._default_end = idx if idx is not None else 0
        # Snapshot the entry labels too: later additions may be INSERTED
        # before a right-aligned native entry rather than appended (see
        # _first_right_index), so restore_defaults must identify extras by
        # label, not by trailing index.
        labels: list[str] = []
        if idx is not None:
            for i in range(idx + 1):
                try:
                    labels.append(self.menubar.entrycget(i, "label"))
                except TclError:
                    pass
        self._default_labels = labels

    def restore_defaults(self):
        """Reset the menubar to the snapshot taken by save_defaults().

        Removes any entries added after the snapshot.  Extras are matched by
        label rather than position: with a right-aligned native entry on the
        bar, post-snapshot cascades are inserted *before* it, so a
        trailing-by-index trim would delete the wrong entries (e.g. the
        right-aligned badge instead of a screen cascade).
        """
        if not hasattr(self, "_default_end") or self._default_end is None:
            return
        current = self.menubar.index("end")
        if current is None:
            self._schedule_native_refresh()
            return
        # Multiset of snapshot labels; walk from the end so deletions don't
        # shift indices we haven't visited yet.  The rightmost occurrence of
        # a duplicated label is kept, which preserves a right-aligned entry.
        remaining: dict[str, int] = {}
        for lbl in getattr(self, "_default_labels", []):
            remaining[lbl] = remaining.get(lbl, 0) + 1
        for i in range(current, -1, -1):
            try:
                label = self.menubar.entrycget(i, "label")
            except TclError:
                continue
            if remaining.get(label, 0) > 0:
                remaining[label] -= 1
                continue
            try:
                self.menubar.delete(i)
            except TclError:
                pass
        self._schedule_native_refresh()

    # ── Native menubar (Windows) ──────────────────────────────────────────────

    @staticmethod
    def native_menubar_supported() -> bool:
        """Whether native menubar patching (bitmaps / right-align) works here.

        ``True`` only on Windows — see ``Widgets/_MenuNative.py``.
        """
        from VIStk.Widgets import _MenuNative
        return _MenuNative.available()

    @staticmethod
    def native_menu_height() -> int:
        """Height of the native menu bar strip in pixels.

        ``SM_CYMENU`` on Windows; falls back to ``20`` elsewhere.  Useful
        for sizing a bitmap to the bar (see :meth:`add_project_command`).
        """
        from VIStk.Widgets import _MenuNative
        return _MenuNative.menu_height()

    def set_native_image(self, label: str, pil_image) -> bool:
        """Swap the native bitmap on an existing entry, in place.

        Renders *pil_image* to a new ``HBITMAP`` and sets it with
        ``SetMenuItemInfo`` directly — the Tk entry is **not** touched, so Tk
        does not rebuild the native menu (an ``entryconfigure`` would drop
        every native patch and cause a visible rebuild).  The replaced
        ``HBITMAP`` is freed after the swap.

        Args:
            label:     Label of an entry previously added through
                       :meth:`add_project_command` with a PIL image (or
                       ``align="right"``) — i.e. one with a registered
                       native patch.
            pil_image: The new ``PIL.Image.Image`` to show.

        Returns:
            ``True`` on success; ``False`` off-Windows, for an unknown /
            unresolvable *label*, or on any native failure.
        """
        from VIStk.Widgets import _MenuNative
        if not _MenuNative.available():
            return False
        patch = self._native_patches.get(label)
        if patch is None:
            return False
        try:
            idx = self.menubar.index(label)
        except TclError:
            return False
        if idx is None:
            return False
        hbitmap = _MenuNative.pil_to_hbitmap(pil_image)
        if hbitmap is None:
            return False
        if not _MenuNative.patch(self._parent, idx, hbitmap=hbitmap,
                                 right=patch.get("right", False)):
            _MenuNative.delete_hbitmap(hbitmap)
            return False
        old = patch.get("hbitmap")
        patch["image"] = pil_image
        patch["hbitmap"] = hbitmap
        if old:
            _MenuNative.delete_hbitmap(old)
        return True

    def refresh_native(self):
        """Re-apply every registered native patch to the menubar, now.

        Tk rebuilds the native menu whenever the Tk menu is mutated,
        resetting ``hbmpItem`` and ``fType`` — this walks
        ``self._native_patches`` and re-applies each by the entry's *current*
        index.  Entries whose label no longer resolves (e.g. deleted by
        :meth:`clear_project_items` / :meth:`restore_defaults`) are skipped.

        Called automatically (coalesced via ``after_idle``) after every
        menubar-mutating method; public as an escape hatch for callers that
        mutate ``self.menubar`` directly.
        """
        from VIStk.Widgets import _MenuNative
        if not _MenuNative.available() or not self._native_patches:
            return
        for label, patch in self._native_patches.items():
            try:
                idx = self.menubar.index(label)
            except TclError:
                continue
            if idx is None:
                continue
            if patch.get("hbitmap") is None and patch.get("image") is not None:
                patch["hbitmap"] = _MenuNative.pil_to_hbitmap(patch["image"])
            hbitmap = patch.get("hbitmap")
            if hbitmap and _MenuNative.current_hbitmap(
                    self._parent, idx) == hbitmap:
                # Patch intact — Tk resets hbmpItem and fType together, so
                # a surviving bitmap means the justify flag survived too.
                continue
            _MenuNative.patch(self._parent, idx, hbitmap=hbitmap,
                              right=patch.get("right", False))

    def _schedule_native_refresh(self):
        """Queue one coalesced :meth:`refresh_native` on the Tk idle loop.

        Every menubar-mutating method ends here; the pending flag collapses
        a burst of mutations (e.g. a full ``configure_menu`` pass) into a
        single re-patch after Tk has rebuilt the native menu.
        """
        if not self._native_patches or self._native_refresh_pending:
            return
        self._native_refresh_pending = True
        try:
            self._parent.after_idle(self._do_native_refresh)
        except TclError:
            self._native_refresh_pending = False

    def _do_native_refresh(self):
        """after_idle target: clear the pending flag and re-patch."""
        self._native_refresh_pending = False
        try:
            if not self._parent.winfo_exists():
                return
            self.refresh_native()
        except TclError:
            pass

    def _first_right_index(self):
        """Menubar index of the leftmost right-aligned entry, or ``None``.

        ``MFT_RIGHTJUSTIFY`` right-aligns its item *and every item after
        it*, so new left-side entries must be inserted before this index
        rather than appended.
        """
        indices = []
        for label, patch in self._native_patches.items():
            if not patch.get("right"):
                continue
            try:
                idx = self.menubar.index(label)
            except TclError:
                continue
            if idx is not None:
                indices.append(idx)
        return min(indices) if indices else None

    def _on_map(self, event):
        """Re-apply native patches when the window (re)maps.

        Deferred through :meth:`_schedule_native_refresh` rather than run
        inline: mapping recreates the Tk wrapper window (the HWND changes)
        and the menu isn't attached to the new wrapper yet when ``<Map>``
        fires — ``GetMenu`` still returns 0 at that instant.
        """
        if event.widget is not self._parent:
            return
        self._schedule_native_refresh()

    def _on_destroy(self, event):
        """Free every native ``HBITMAP`` when the window is destroyed."""
        if event.widget is not self._parent:
            return
        from VIStk.Widgets import _MenuNative
        for patch in self._native_patches.values():
            hbitmap = patch.get("hbitmap")
            patch["hbitmap"] = None
            if hbitmap:
                _MenuNative.delete_hbitmap(hbitmap)

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