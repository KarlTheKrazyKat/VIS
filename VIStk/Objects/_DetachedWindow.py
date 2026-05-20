from __future__ import annotations

from tkinter import Toplevel

from VIStk.Objects._Identity import new_id
from VIStk.Objects._TabManager import TabManager
from VIStk.Widgets._HostMenu import HostMenu
from VIStk.Widgets._InfoRow import InfoRow


class DetachedWindow:
    """A visible application window (Toplevel) containing its own TabManager,
    HostMenu, and InfoRow.

    In the new architecture every visible window is a DetachedWindow.  The
    Host is a hidden Tk root that manages these windows.

    The first DetachedWindow is created by Host.py immediately after the root
    is withdrawn.  Additional windows are created by tab pop-out, drag-detach,
    or opening standalone screens.

    Window title follows ``"project: screen — info"`` format.

    Two-pass close: when the user clicks the X button, ``on_quit`` is called
    on every tab.  Tabs that return ``False`` veto their destruction.  If all
    tabs allow closing, the window is destroyed.
    """

    def __init__(self, host, scr=None,
                 x_root: int | None = None, y_root: int | None = None,
                 btn_offset_x: int = 0, btn_offset_y: int = 0,
                 chromeless: bool = False, args: list | None = None):
        """
        Args:
            host:         The owning ``Host`` instance.
            scr:          ``Screen`` to open as the first tab, or ``None``
                          to create an empty window (used by drag-detach and
                          pop-out, which then call ``move_tab`` to bring an
                          existing tab in with its per-tab namespace intact).
            x_root:       Screen x coordinate for positioning (or None for default).
            y_root:       Screen y coordinate for positioning (or None for default).
            btn_offset_x: Cursor x offset within the original tab button.
            btn_offset_y: Cursor y offset within the original tab button.
            chromeless:   When True, hide the tab bar and use the screen's
                          own icon and name for the window — used by
                          ``Host._open_standalone`` so non-tabbed screens
                          appear as plain windows rather than single-tab
                          windows.
            args:         CLI-style args forwarded to the first tab's
                          ``ArgHandler`` (only used when *scr* is given).
        """
        from VIStk.Objects._Host import _HOST_INSTANCE

        self.id: int = new_id()
        """Stable process-unique window ID (0.4.7)."""

        self.host = host
        self._closing = False
        self.chromeless: bool = chromeless
        """When True the tab bar is hidden and the window adopts the
        screen's own icon and name (set by ``Host._open_standalone``)."""

        # Toplevel on the hidden root
        self.win = Toplevel(host.root)
        self.win.title(host.Project.title)
        self.win.protocol("WM_DELETE_WINDOW", self._on_close)

        # ── Menu bar ──────────────────────────────────────────────────────────
        self.HostMenu = HostMenu(self.win, close_command=self._on_close)
        self.HostMenu.attach()
        if host.default_menu_setup:
            try:
                host.default_menu_setup(self.HostMenu)
            except Exception:
                import traceback
                traceback.print_exc()
        self.HostMenu.save_defaults()

        # ── Tab content area (SplitView for split panes) ──────────────────────
        from VIStk.Widgets._SplitView import SplitView
        self._split_view = SplitView(
            self.win, host=host,
            tab_position=getattr(host.Project, "tab_bar_position", "top"),
        )
        self._split_view.pack(fill="both", expand=True)
        self._split_view.set_callbacks({
            "on_tab_activate":    self._on_tab_activate,
            "on_tab_deactivate":  self._on_tab_deactivate,
            "on_tab_popout":      self._on_tab_popout,
            "on_tab_detach":      self._on_tab_detach,
            "on_tab_refresh":     self._on_tab_refresh,
            "on_tab_info_change": self._on_tab_info_change,
            "on_tab_split":       self._on_tab_split,
        })

        # Track all TabManagers in this window (primary + split panes)
        self.tab_managers: list[TabManager] = [self.tab_manager]

        # Wire TabManager back-references
        self.tab_manager._menubar = self.HostMenu
        self.tab_manager._detached_window = self

        # Register with Host
        host.registered_tab_managers.append(self.tab_manager)
        host.detached_windows.append(self)
        host.active_tab_manager = self.tab_manager

        # ── Status bar ────────────────────────────────────────────────────────
        self.InfoRow = InfoRow(self.win, host.Project)
        self.InfoRow.pack(fill="x", side="bottom")
        host._fps_listeners.append(self.InfoRow.set_fps)

        # Hide the tab bar before laying out the window for chromeless mode
        # so the geometry math sees the final content area.  Lock the
        # SplitView so the chromeless window stays single-pane — splits
        # would re-introduce a tab strip in the new pane and defeat the
        # standalone presentation.  When the active screen opts out of the
        # host menubar via ``host_menubar=False`` in project.json, detach
        # the menubar from the window — the HostMenu object stays alive so
        # screen code that calls ``set_screen_items`` etc. still works.
        if self.chromeless:
            self.tab_manager.hide_tab_bar()
            self._split_view.lock()
            if scr is not None and not scr.host_menubar:
                self.HostMenu.detach()

        # Set window icon — chromeless windows use the screen's icon
        # rather than the project default.
        self._load_icon(scr.name if (self.chromeless and scr is not None) else None)

        # Bind focus tracking
        self.win.bind("<FocusIn>", self._on_window_focus)

        # Open the first tab if a screen was provided.  TabManager.open_screen
        # builds the per-tab namespace and exec's the entry script into it.
        if scr is not None:
            icon = host._load_tab_icon(scr)
            display = host._unique_display_name(scr.name)
            self.tab_manager.open_screen(scr, display, icon=icon, args=args)

        # Position window
        if x_root is not None and y_root is not None:
            self._position_window(x_root, y_root, btn_offset_x, btn_offset_y)
        else:
            # Default: center on screen, with a cascade offset so additional
            # windows don't sit exactly on top of the first one.
            self.win.geometry("1200x800")
            self.win.update_idletasks()
            sw = self.win.winfo_screenwidth()
            sh = self.win.winfo_screenheight()
            cascade = max(0, len(host.detached_windows) - 1) * 30
            x = (sw - 1200) // 2 + cascade
            y = (sh - 800) // 2 + cascade
            self.win.geometry(f"+{x}+{y}")

    # ── Property shim ─────────────────────────────────────────────────────────

    @property
    def tab_manager(self) -> TabManager:
        """Return the focused pane's TabManager."""
        return self._split_view.focused_pane

    # ── Focus tracking ────────────────────────────────────────────────────────

    def _on_window_focus(self, event):
        if event.widget is self.win:
            self.host.active_tab_manager = self.tab_manager

    def focus_force(self):
        """Bring this window to the front and focus it."""
        try:
            self.win.deiconify()
            self.win.lift()
            self.win.focus_force()
        except Exception:
            pass

    # ── Positioning ────────────────────────────────────────────────────────────

    def _position_window(self, x_root: int, y_root: int,
                         btn_offset_x: int, btn_offset_y: int):
        """Position the window so the cursor sits over the new tab at the same offset."""
        try:
            self.win.geometry("1200x800+0+0")
            self.win.update_idletasks()

            tab_ids = list(self.tab_manager._tabs.keys())
            if tab_ids:
                btn = self.tab_manager.tab_bar._tabs[tab_ids[0]]["button"]
                btn_in_win_x, btn_in_win_y = 0, 0
                w = btn
                while True:
                    btn_in_win_x += w.winfo_x()
                    btn_in_win_y += w.winfo_y()
                    p = w.winfo_parent()
                    if not p or p == str(self.win):
                        break
                    w = w.nametowidget(p)

                win_x = x_root - btn_offset_x - btn_in_win_x
                win_y = y_root - btn_offset_y - btn_in_win_y
                self.win.geometry(f"+{win_x}+{win_y}")
        except Exception:
            pass

    def _load_icon(self, screen_name: str | None = None):
        """Set the window's taskbar icon.

        When ``screen_name`` is provided and the screen has its own icon,
        use it; otherwise fall back to the project default icon.  Used by
        chromeless standalone windows to advertise the screen identity in
        the taskbar instead of the project identity.
        """
        try:
            import glob as _glob
            import PIL.Image
            import PIL.ImageTk

            icon_name: str | None = None
            if screen_name:
                scr = self.host.Project.getScreen(screen_name)
                if scr is not None and scr.icon:
                    icon_name = scr.icon
            if icon_name is None:
                icon_name = self.host.Project.d_icon

            matches = _glob.glob(self.host.Project.p_icons + "/" + icon_name + ".*")
            if matches:
                img = PIL.Image.open(matches[0]).convert("RGBA").resize((32, 32))
                # Hold a reference so Tk doesn't garbage-collect the image.
                self._icon_ref = PIL.ImageTk.PhotoImage(img)
                self.win.iconphoto(True, self._icon_ref)
        except Exception:
            pass

    # ── Lifecycle callbacks (tab events) ──────────────────────────────────────

    def _on_tab_activate(self, tab_id: int, module):
        """Update title, InfoRow, and menu when a tab gains focus."""
        self.HostMenu.restore_defaults()
        self.HostMenu.clear_screen_items()

        entry = self.tab_manager._tabs.get(tab_id, {})
        display = entry.get("display_name", "")
        info = entry.get("info", "")
        self._set_title(display, info)
        base_name = entry.get("base_name", display)
        scr = self.host.Project.getScreen(base_name)
        self.InfoRow.set_screen(display, str(scr.s_version) if scr else "")

        # Route configure_menu through TabManager
        self.tab_manager._call_configure_menu(tab_id)

        # Apply MENU_OVERRIDES if present on the per-tab namespace
        overrides = getattr(module, "MENU_OVERRIDES", None)
        if overrides:
            try:
                self.HostMenu.apply_overrides(overrides)
            except Exception:
                pass

    def _on_tab_deactivate(self, tab_id: int | None):
        self.HostMenu.restore_defaults()
        self.HostMenu.clear_screen_items()
        if tab_id is None:
            self.win.title(self.host.Project.title)
            self.InfoRow.set_screen("")

    def _on_tab_info_change(self, tab_id: int, info: str):
        if self.tab_manager.active == tab_id:
            entry = self.tab_manager._tabs.get(tab_id, {})
            self._set_title(entry.get("display_name", ""), info)

    def _set_title(self, screen: str, info: str = ""):
        if self.chromeless:
            # Standalone windows advertise the screen identity directly
            # rather than the project: screen prefix used for the tabbed
            # Host shell.
            self.win.title(f"{screen} — {info}" if info else screen)
            return
        base = self.host.Project.title
        if info:
            self.win.title(f"{base}: {screen} — {info}")
        else:
            self.win.title(f"{base}: {screen}")

    # ── Pop-out, detach, refresh, split ───────────────────────────────────────

    def _on_tab_popout(self, tab_id: int):
        """Pop out a tab into a new DetachedWindow at cursor position.

        Uses ``move_tab`` so the per-tab namespace and in-tab state
        survive the pop-out — the user expects to find their work in
        the new window, not a fresh-loaded screen.
        """
        pane = self._split_view.find_pane_for_tab(tab_id)
        if pane is None:
            return
        x = self.win.winfo_pointerx()
        y = self.win.winfo_pointery()
        self._create_detached(pane, tab_id, x, y, 0, 0)

    def _on_tab_detach(self, tab_id: int):
        """Handle drag-to-detach — use pointer position and stored offsets."""
        pane = self._split_view.find_pane_for_tab(tab_id)
        if pane is None:
            return
        bx = pane.tab_bar._last_drag_btn_offset_x
        by = pane.tab_bar._last_drag_btn_offset_y
        x = self.win.winfo_pointerx()
        y = self.win.winfo_pointery()
        self._create_detached(pane, tab_id, x, y, bx, by)

    def _create_detached(self, source_pane, tab_id: int,
                         x_root, y_root, btn_offset_x, btn_offset_y):
        """Create an empty new DetachedWindow and move *tab_id* into it.

        The empty window is positioned so the cursor lands over the
        moved tab's button at the same offset the drag started with.
        """
        dw = DetachedWindow(self.host, scr=None,
                            x_root=x_root, y_root=y_root,
                            btn_offset_x=btn_offset_x,
                            btn_offset_y=btn_offset_y)
        dw.tab_manager.move_tab(source_pane, tab_id)

    def _on_tab_refresh(self, tab_id: int):
        """Refresh delegates to TabManager.force_refresh_tab.

        The previous override exists only because force_refresh_tab
        couldn't resolve the Screen object itself; it now does, so the
        override is a one-line delegation.
        """
        pane = self._split_view.find_pane_for_tab(tab_id)
        if pane is None:
            return
        pane.force_refresh_tab(tab_id)

    def _on_tab_split(self, tab_id: int, direction: str, target_pane=None):
        """Handle right-click 'Split right' / 'Split down' or drag-to-split."""
        from VIStk.Widgets._SplitView import SplitView

        source_pane = self._split_view.find_pane_for_tab(tab_id)
        if source_pane is None:
            return
        split_pane = target_pane if target_pane is not None else source_pane

        target_sv = SplitView.find_owner(split_pane)
        if target_sv is None:
            target_sv = self._split_view

        if direction == "center":
            # Merge into an existing pane — namespace must survive.
            if split_pane is source_pane:
                return
            split_pane.move_tab(source_pane, tab_id)
        elif split_pane is source_pane:
            # Same-pane split: the source pane splits into left/right;
            # everything except this tab transfers to left_pane, then we
            # place this tab in right_pane.  SplitView.split() preserves
            # module references for non-excluded tabs; the excluded tab's
            # per-tab namespace stays alive in sys.modules through the
            # destroy-and-reopen because we never call close_tab.
            if len(source_pane._tabs) <= 1:
                return
            entry = source_pane._tabs[tab_id]
            display   = entry["display_name"]
            module    = entry.get("module")
            icon      = entry.get("icon")
            base_name = entry.get("base_name", display)
            _, right_pane = target_sv.split(
                split_pane, direction, exclude={tab_id})
            right_pane.open_tab(display, module, icon=icon,
                                base_name=base_name, tab_id=tab_id)
        else:
            # Cross-pane split: split the destination first, then move the
            # tab from source_pane into the new right_pane (namespace
            # preserved via move_tab).
            _, right_pane = target_sv.split(split_pane, direction)
            right_pane.move_tab(source_pane, tab_id)

    # ── SplitView pane callbacks ──────────────────────────────────────────────

    def _create_pane(self, position):
        """Callback from SplitView when a new pane is requested."""
        from VIStk.Objects._Host import _HOST_INSTANCE
        tm = TabManager(self._split_view, menubar=self.HostMenu)
        tm._detached_window = self
        if _HOST_INSTANCE:
            _HOST_INSTANCE.registered_tab_managers.append(tm)
        self.tab_managers.append(tm)
        return tm

    def _destroy_pane(self, tab_manager):
        """Callback from SplitView when a pane is removed."""
        from VIStk.Objects._Host import _HOST_INSTANCE
        tab_manager._cleanup_all_modules()
        if _HOST_INSTANCE:
            try:
                _HOST_INSTANCE.registered_tab_managers.remove(tab_manager)
            except ValueError:
                pass
        try:
            self.tab_managers.remove(tab_manager)
        except ValueError:
            pass
        tab_manager.destroy()

    # ── Window close — two-pass with on_quit ──────────────────────────────────

    def _on_close(self):
        """Close all tabs and remove from Host tracking.

        Two-pass close: first check all tabs for on_quit vetoes, then
        destroy tabs that did not veto.  If nothing vetoed, destroy window.
        """
        from VIStk.Objects._Host import _HOST_INSTANCE
        if self._closing:
            return
        self._closing = True

        # (0.4.7) Iterate the live SplitView tree rather than
        # ``self.tab_managers``, which is seeded at init and never
        # maintained across splits — the seeded-only list misses every
        # pane created by ``SplitView.split`` and every pane rebuilt by
        # ``SplitView.remove_pane``, causing on_quit vetoes to be
        # silently skipped in those panes.
        live_panes = list(self._split_view.all_tab_managers())

        # Pass 1: collect vetoes (by tab_id).  Under the per-tab namespace
        # design hooks live inside ``module`` (the per-tab namespace) —
        # no separate hooks key to consult.
        vetoed: set[int] = set()
        for tm in live_panes:
            for tab_id, tab in list(tm._tabs.items()):
                module = tab.get("module")
                quit_fn = getattr(module, "on_quit", None)
                if quit_fn:
                    try:
                        if quit_fn() is False:
                            vetoed.add(tab_id)
                    except Exception:
                        pass

        # Pass 2: destroy tabs that did not veto
        for tm in live_panes:
            for tab_id in list(tm._tabs.keys()):
                if tab_id not in vetoed:
                    tm.close_tab(tab_id, skip_on_quit=True)

        # If nothing vetoed, destroy window
        if vetoed:
            self._closing = False
            return

        # Deregister all TabManagers
        for tm in self.tab_managers:
            if _HOST_INSTANCE:
                try:
                    _HOST_INSTANCE.registered_tab_managers.remove(tm)
                except ValueError:
                    pass

        # Deregister FPS listener
        if _HOST_INSTANCE:
            try:
                _HOST_INSTANCE._fps_listeners.remove(self.InfoRow.set_fps)
            except (ValueError, AttributeError):
                pass

        try:
            self.win.destroy()
        except Exception:
            pass

        if _HOST_INSTANCE:
            try:
                _HOST_INSTANCE.detached_windows.remove(self)
            except ValueError:
                pass
