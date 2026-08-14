from __future__ import annotations

from tkinter import Toplevel, TclError

from VIStk.Objects._Identity import new_id
from VIStk.Objects._TabManager import TabManager
from VIStk.Widgets._HostMenu import HostMenu
from VIStk.Widgets._InfoRow import InfoRow


# Process-wide cache of title-bar HICON handles, keyed by icon name.  The
# handles must outlive the WM_SETICON call (Windows does not copy the icon),
# so they are built at most once per name and never released for the life of
# the process.
_HICON_CACHE: dict[str, int] = {}


def _titlebar_hicon(icons_dir: str, icon_name: str) -> int:
    """Build (and cache) a 16×16 HICON for ``icon_name`` from ``icons_dir``.

    The source may be any PIL-readable image (PNG, ICO, …) matched by
    ``<icons_dir>/<icon_name>.*``.  It is rendered to a small ICO in the temp
    directory and loaded with ``LoadImageW``; the handle is cached.  Returns
    the HICON, or ``0`` on failure.  Windows-only — callers guard on platform.
    """
    if icon_name in _HICON_CACHE:
        return _HICON_CACHE[icon_name]
    import glob as _glob, os, tempfile, ctypes
    import PIL.Image

    handle = 0
    matches = _glob.glob(icons_dir + "/" + icon_name + ".*")
    if matches:
        ico_path = os.path.join(tempfile.gettempdir(),
                                f"_vistk_titlebar_{icon_name}.ico")
        try:
            PIL.Image.open(matches[0]).convert("RGBA").save(
                ico_path, format="ICO", sizes=[(16, 16), (24, 24), (32, 32)])
            IMAGE_ICON, LR_LOADFROMFILE = 1, 0x00000010
            handle = ctypes.windll.user32.LoadImageW(
                None, ico_path, IMAGE_ICON, 16, 16, LR_LOADFROMFILE)
        except Exception:
            handle = 0
    _HICON_CACHE[icon_name] = handle
    return handle


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
        # Framework-provided persistent Settings entry (0.6.0) — opt-in via
        # project.json  host.settings_menu  (default false).  An app that wants
        # it sets that flag true; PYWOM and others get no Settings entry.
        if getattr(host.Project, "host_settings_menu", False):
            try:
                self.HostMenu.add_project_command("Settings", host._open_settings)
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

        # Mount any app-registered menubar accessories (e.g. a current-user
        # badge) into the primary pane's tab-bar right corner.  Splits create
        # fresh panes without accessories, so this stays one-per-window.
        try:
            host._mount_menubar_accessories(self.tab_manager.tab_bar)
        except Exception:
            import traceback
            traceback.print_exc()

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

        # Position window.  An explicit drop point (drag-detach / pop-out)
        # is honoured verbatim; otherwise apply the project's window
        # application settings (first window) or the legacy cascade default.
        if x_root is not None and y_root is not None:
            self._position_window(x_root, y_root, btn_offset_x, btn_offset_y)
        else:
            self._apply_startup_geometry()

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
        """Set the window's taskbar and title-bar icons independently.

        Windows exposes two icon slots that this method fills separately:

        * **Taskbar** (``ICON_BIG``) — the screen's own ``icon`` when
          ``screen_name`` is given (a chromeless standalone window), else
          the project :attr:`~VIStk.Structures._Project.Project.d_icon`.
          Applied with ``iconphoto`` (also the cross-platform icon).
        * **Title bar** (``ICON_SMALL``) — the project-level
          :attr:`~VIStk.Structures._Project.Project.d_window_icon`.  For a
          chromeless standalone window a screen may override it with its own
          ``window_icon``; tabbed screens share a chromed window (their
          ``screen_name`` is never passed here) and therefore cannot repaint
          it.  Applied via ``WM_SETICON`` on Windows only — on other
          platforms the title bar shares the taskbar image.

        ``d_window_icon`` unset (the default) leaves the title bar sharing
        the taskbar image, preserving prior behavior.
        """
        try:
            import glob as _glob
            import PIL.Image
            import PIL.ImageTk

            proj = self.host.Project
            scr = proj.getScreen(screen_name) if screen_name else None

            # ── Taskbar icon (ICON_BIG) ────────────────────────────────
            icon_name = scr.icon if (scr is not None and scr.icon) else None
            if icon_name is None:
                icon_name = proj.d_icon
            matches = _glob.glob(proj.p_icons + "/" + icon_name + ".*")
            if matches:
                img = PIL.Image.open(matches[0]).convert("RGBA").resize((32, 32))
                # Hold a reference so Tk doesn't garbage-collect the image.
                self._icon_ref = PIL.ImageTk.PhotoImage(img)
                self.win.iconphoto(True, self._icon_ref)

            # ── Title-bar icon (ICON_SMALL) ────────────────────────────
            # d_window_icon is the only project-level title-bar setter; a
            # per-screen window_icon overrides it *only* for a chromeless
            # standalone window (scr is non-None only then).
            win_icon_name = getattr(proj, "d_window_icon", None)
            if scr is not None and getattr(scr, "window_icon", None):
                win_icon_name = scr.window_icon
            if win_icon_name:
                self._apply_titlebar_icon(win_icon_name)
        except Exception:
            pass

    def _apply_titlebar_icon(self, icon_name: str):
        """Override this window's title-bar icon (``ICON_SMALL``) on Windows.

        No-op on non-Windows platforms, where the title bar shares the
        taskbar image set by ``iconphoto``.  The HICON is cached process-wide
        and referenced on the window so it is neither rebuilt per call nor
        garbage-collected (``WM_SETICON`` does not copy the icon).
        """
        import sys
        if sys.platform != "win32":
            return
        try:
            import ctypes
            hicon = _titlebar_hicon(self.host.Project.p_icons, icon_name)
            if not hicon:
                return
            self.win.update_idletasks()
            # A Tk Toplevel's winfo_id() is the content HWND; its parent is
            # the decorated frame that owns the title-bar icon.
            hwnd = ctypes.windll.user32.GetParent(self.win.winfo_id())
            WM_SETICON, ICON_SMALL = 0x0080, 0
            ctypes.windll.user32.SendMessageW(hwnd, WM_SETICON, ICON_SMALL, hicon)
            self._titlebar_hicon_ref = hicon
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
        self._set_title(display, info, replace=entry.get("replace_label", False))
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
            self._set_title(entry.get("display_name", ""), info,
                            replace=entry.get("replace_label", False))

    def _set_title(self, screen: str, info: str = "", replace: bool = False):
        # A tab opted into replace already supplies a complete label ("WO
        # 21930") that carries the screen's identity, so prefixing the screen
        # name would only repeat it — mirror the tab bar and use info alone.
        if replace and info:
            label = info
        elif info:
            label = f"{screen} — {info}"
        else:
            label = screen

        if self.chromeless:
            # Standalone windows advertise the screen identity directly
            # rather than the project: screen prefix used for the tabbed
            # Host shell.
            self.win.title(label)
            return
        self.win.title(f"{self.host.Project.title}: {label}")

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

    # ── Startup geometry (application settings, 0.6.0) ─────────────────────────

    def _apply_startup_geometry(self) -> None:
        """Size and place a window opened without explicit drop coordinates.

        The first window of a session honours the project's ``window.*``
        application settings — default size, minimum size, alignment,
        restored last geometry, and fullscreen-on-launch.  Later windows
        keep the legacy centred default with a per-window cascade offset so
        they don't stack exactly on top of one another.
        """
        host = self.host
        settings = host.Project.Settings

        w = settings.get("window.default_width") or 1200
        h = settings.get("window.default_height") or 800
        try:
            w, h = int(w), int(h)
        except (TypeError, ValueError):
            w, h = 1200, 800
        # Guard against non-positive sizes (hand-edited settings.json) that
        # would produce an invalid Tk geometry string.
        if w <= 0:
            w = 1200
        if h <= 0:
            h = 800

        # Minimum size — applied to every window when configured.
        mw, mh = settings.get("window.min_width"), settings.get("window.min_height")
        if mw and mh:
            try:
                self.win.minsize(int(mw), int(mh))
            except Exception:
                pass

        # Track the session's first window as the primary regardless of
        # chromeless state — chromeless governs tab-bar/title presentation,
        # not whether geometry should be remembered/restored.
        first = len(host.detached_windows) == 1
        if first:
            host._primary_window = self
            self._apply_primary_geometry(settings, w, h)
        else:
            self.win.geometry(f"{w}x{h}")
            self.win.update_idletasks()
            cascade = max(0, len(host.detached_windows) - 1) * 30
            x, y = self._aligned_xy(w, h, "center")
            self.win.geometry(f"+{x + cascade}+{y + cascade}")

    def _apply_primary_geometry(self, settings, w: int, h: int) -> None:
        """Apply size/position to the session's first window from settings."""
        if settings.get("window.remember_geometry"):
            saved = settings.get("window.last_geometry")
            if saved:
                try:
                    self.win.geometry(saved)
                    return
                except Exception:
                    pass

        self.win.geometry(f"{w}x{h}")
        self.win.update_idletasks()
        align = settings.get("window.default_align") or "center"
        x, y = self._aligned_xy(w, h, align)
        self.win.geometry(f"+{x}+{y}")

        if settings.get("window.fullscreen_on_launch"):
            self._zoom_window()

    def _aligned_xy(self, w: int, h: int, align: str) -> tuple[int, int]:
        """Top-left ``(x, y)`` placing a *w*×*h* window at compass *align*."""
        sw = self.win.winfo_screenwidth()
        sh = self.win.winfo_screenheight()
        cx, cy = (sw - w) // 2, (sh - h) // 2
        right, bottom = sw - w, sh - h
        return {
            "center": (cx, cy),
            "n":  (cx, 0),   "ne": (right, 0),    "e":  (right, cy),
            "se": (right, bottom), "s": (cx, bottom), "sw": (0, bottom),
            "w":  (0, cy),   "nw": (0, 0),
        }.get(align, (cx, cy))

    def _zoom_window(self) -> None:
        """Maximise the window cross-platform (mirrors ``Window.fullscreen``)."""
        try:  # Linux
            self.win.wm_attributes("-zoomed", True)
        except TclError:  # Windows
            try:
                self.win.state("zoomed")
            except Exception:
                pass

    def _snapshot_base_names(self) -> list[str]:
        """Ordered ``base_name`` of every tab in this window (all panes).

        Captured before the close tear-down destroys the tabs, so the Host
        can persist the session for ``host.remember_tabs``.
        """
        out: list[str] = []
        for tm in self._split_view.all_tab_managers():
            for tab in tm._tabs.values():
                b = tab.get("base_name")
                if b:
                    out.append(b)
        return out

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

        # Capture the session BEFORE the tear-down destroys the tabs, so the
        # Host can persist "remember open tabs" on the normal user-close path.
        captured = self._snapshot_base_names()

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

        # Persist session state when this is the last window closing under a
        # normal user close.  quit_host() snapshots all windows up-front and
        # sets _shutting_down, so we must not clobber that full snapshot with
        # this single window's subset.
        if _HOST_INSTANCE is not None and not _HOST_INSTANCE._shutting_down \
                and len(_HOST_INSTANCE.detached_windows) == 1:
            _HOST_INSTANCE._persist_session(open_tabs=captured, geo_window=self)

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
