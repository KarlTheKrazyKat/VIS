from __future__ import annotations

import importlib
import importlib.util
import os
import queue
import sys
import time
from tkinter import Tk

from VIStk.Structures._Project import Project

# Module-level singleton reference — set by Host.__init__, cleared on quit.
_HOST_INSTANCE: "Host | None" = None


class Host:
    """Application host that owns a hidden Tk root.

    The Host is not a visible window.  It creates a ``Tk()`` root, withdraws
    it immediately, and manages ``DetachedWindow`` instances (Toplevels) for
    all visible application windows.

    Navigation routes through ``_HOST_INSTANCE`` in-process.  There is no
    IPC layer and no system tray.

    Attributes:
        root                  (Tk):            The hidden Tk root.
        Project               (Project):       The VIS project.
        registered_tab_managers (list):         All active TabManager instances.
        active_tab_manager    (TabManager|None): The most recently focused pane.
        detached_windows      (list):          All live DetachedWindow instances.
        default_menu_setup    (callable|None):  Called on every new window's menubar.
        fps                   (float):         Current frames per second.
    """

    def __init__(self):
        global _HOST_INSTANCE

        self.root = Tk()
        self.root.withdraw()

        self.Project = Project()

        # Set the hidden root title (shows in taskbar if accidentally mapped)
        self.root.title(self.Project.title)

        self.registered_tab_managers: list = []
        self.active_tab_manager = None
        self.detached_windows: list = []
        self.default_menu_setup = None

        # FPS tracking
        self.fps: float = 0.0
        self._fps_last: float = time.time()
        self._fps_frames: int = 0
        self._fps_acc: float = 0.0
        self._fps_listeners: list = []

        # (0.4.7) Multiple-instance tracking retired — tab IDs now make
        # every tab uniquely addressable; label uniqueness is only a UX
        # concern, handled by :meth:`_unique_display_name`.
        self.Active: bool = True

        self._opened_default = False

        _HOST_INSTANCE = self

    # ── Navigation ─────────────────────────────────────────────────────────────

    def open(self, screen_name: str):
        """Unified navigation entry point.

        Tabbed screens open as tabs in the active TabManager's window.
        Standalone (tabbed=False) screens open as new DetachedWindows.
        When running from a compiled installation, refuses to open a
        screen whose binary is not present on disk and shows an inline
        banner in the active window's InfoRow instead.
        """
        scr = self.Project.getScreen(screen_name)
        if scr is None:
            return
        if not self._check_installed(scr):
            return
        if scr.tabbed:
            self._open_tab(scr)
        else:
            self._open_standalone(scr)

    def _check_installed(self, scr) -> bool:
        """Return True if ``scr`` can be opened; show a banner and return
        False when running from a frozen build that's missing the binary."""
        from VIStk.Structures._Install import is_screen_installed
        if is_screen_installed(scr.name):
            return True
        msg = getattr(scr, "warn_message", None) or (
            f"'{scr.name}' is not installed. "
            "Reinstall and select it to enable this feature."
        )
        dw = self._active_detached_window()
        if dw is not None:
            try:
                dw.InfoRow.show_banner(msg, level="warn")
            except Exception:
                pass
        return False

    def _active_detached_window(self):
        """Return the DetachedWindow that owns ``active_tab_manager``, or
        the first open window as fallback."""
        for dw in self.detached_windows:
            if self.active_tab_manager in dw.tab_managers:
                return dw
        return self.detached_windows[0] if self.detached_windows else None

    # ── Tabs ───────────────────────────────────────────────────────────────────

    def _get_all_tab_labels(self) -> set[str]:
        """Return every display label currently in use across all windows.

        Used by :meth:`_unique_display_name` to avoid visually ambiguous
        duplicate labels; internal bookkeeping relies on tab IDs (0.4.7),
        not on label uniqueness.

        Walks the live SplitView tree rather than ``dw.tab_managers`` so
        ghost labels from TabManagers destroyed by ``SplitView.remove_pane``
        (a pre-existing bookkeeping leak) don't trigger spurious ``(2)``
        suffixes on new tabs.
        """
        labels: set[str] = set()
        for dw in self.detached_windows:
            for tm in dw._split_view.all_tab_managers():
                for entry in tm._tabs.values():
                    label = entry.get("display_name")
                    if label:
                        labels.add(label)
        return labels

    def _find_tab_by_base(self, base_name: str):
        """Return ``(tab_manager, tab_id)`` for the first open tab whose
        ``base_name`` matches, else ``(None, None)``.

        With duplicate base names this picks the first match — callers
        wanting a specific instance should hold the tab_id returned by
        :meth:`TabManager.open_tab`.

        Walks the live SplitView tree so ghost entries from destroyed
        TabManagers (see ``_get_all_tab_labels``) aren't returned.
        """
        for dw in self.detached_windows:
            for tm in dw._split_view.all_tab_managers():
                for tab_id, entry in tm._tabs.items():
                    display = entry.get("display_name", "")
                    if entry.get("base_name", display) == base_name:
                        return tm, tab_id
        return None, None

    def _unique_display_name(self, base: str) -> str:
        """Return a display name that doesn't visually collide with an
        already-open tab label."""
        existing = self._get_all_tab_labels()
        if base not in existing:
            return base
        n = 2
        while f"{base} ({n})" in existing:
            n += 1
        return f"{base} ({n})"

    def _open_tab(self, scr):
        if scr.single_instance:
            tm, tab_id = self._find_tab_by_base(scr.name)
            if tm is not None and tab_id is not None:
                tm.focus_tab(tab_id)
                # Raise the DetachedWindow that owns the target pane
                for dw in self.detached_windows:
                    if tm in dw.tab_managers:
                        try:
                            dw.win.deiconify()
                            dw.win.lift()
                            dw.win.focus_force()
                        except Exception:
                            pass
                        break
                return

        # Enforce max_tabs limit
        max_t = getattr(self.Project, "max_tabs", None)
        if max_t is not None:
            from tkinter import messagebox
            total = sum(len(tm._tabs) for tm in self.registered_tab_managers)
            if total >= max_t:
                messagebox.showinfo(
                    "Tab limit reached",
                    f"Maximum {max_t} tab{'s' if max_t != 1 else ''} are already open.\n"
                    "Close a tab to open another."
                )
                return

        display = self._unique_display_name(scr.name)
        module = self._import_screen(scr)
        hooks = self._import_hooks(scr)
        icon = self._load_tab_icon(scr)

        # Open in the active TabManager, or the first window's primary pane
        target = self.active_tab_manager
        if target is None and self.detached_windows:
            target = self.detached_windows[0].tab_manager
        if target is None:
            # No window exists yet — create one
            from VIStk.Objects._DetachedWindow import DetachedWindow
            dw = DetachedWindow(self, module, scr.name)
            return

        target.open_tab(display, module, hooks=hooks, icon=icon,
                        base_name=scr.name)

    def _open_standalone(self, scr):
        """Open a standalone (tabbed=False) screen as a new DetachedWindow."""
        module = self._import_screen(scr)
        if module is None:
            return
        from VIStk.Objects._DetachedWindow import DetachedWindow
        dw = DetachedWindow(self, module, scr.name)

    def _load_tab_icon(self, scr) -> "PIL.ImageTk.PhotoImage | None":
        if not scr.icon:
            return None
        try:
            import glob as _glob
            import PIL.Image
            import PIL.ImageTk
            from PIL.Image import Resampling
            matches = _glob.glob(self.Project.p_icons + "/" + scr.icon + ".*")
            if not matches:
                return None
            img = (PIL.Image.open(matches[0])
                   .convert("RGBA")
                   .resize((16, 16), Resampling.LANCZOS))
            return PIL.ImageTk.PhotoImage(img)
        except Exception:
            return None

    # ── Screen import ──────────────────────────────────────────────────────────

    def _import_screen(self, scr):
        script_path = self.Project.p_project + "/" + scr.script
        project_dir = self.Project.p_project
        try:
            if project_dir not in sys.path:
                sys.path.insert(0, project_dir)
            spec = importlib.util.spec_from_file_location(scr.name, script_path)
            if spec is None:
                return None
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            return mod
        except Exception:
            return None

    def _import_hooks(self, scr):
        name = scr.name
        hooks_path = self.Project.p_project + f"/modules/{name}/m_{name}.py"
        try:
            if not os.path.exists(hooks_path):
                return None
            project_dir = self.Project.p_project
            if project_dir not in sys.path:
                sys.path.insert(0, project_dir)
            spec = importlib.util.spec_from_file_location(
                f"modules.{name}.m_{name}", hooks_path
            )
            if spec is None:
                return None
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            return mod
        except Exception:
            return None

    # ── FPS ────────────────────────────────────────────────────────────────────

    def tick_fps(self):
        """Call once per update loop iteration to maintain the fps counter."""
        now = time.time()
        dt = now - self._fps_last
        self._fps_last = now
        self._fps_frames += 1
        self._fps_acc += dt
        if self._fps_acc >= 1.0:
            self.fps = self._fps_frames / self._fps_acc
            self._fps_frames = 0
            self._fps_acc = 0.0
            for listener in list(self._fps_listeners):
                try:
                    listener(self.fps)
                except Exception:
                    pass

    def update(self):
        """Process all pending Tk events for the root and its Toplevels.

        On the first call, opens the default screen so that Host.py has
        time to configure ``default_menu_setup`` before any window is created.
        """
        if not self._opened_default:
            self._opened_default = True
            if self.Project.default_screen:
                self.open(self.Project.default_screen)
        self.root.update()

    def quit_host(self):
        """Close all DetachedWindows one by one, then shut down.

        Each window's ``_on_close()`` runs the two-pass veto check.  If any
        window vetoes (e.g. unsaved changes), the shutdown stops and the
        Host stays alive.
        """
        for dw in list(self.detached_windows):
            dw._on_close()
            if dw in self.detached_windows:
                # Window vetoed — abort shutdown
                return

        self.Active = False
        try:
            self.root.destroy()
        except Exception:
            pass

    # ── Startup registration (opt-in) ─────────────────────────────────────────

    def _register_startup(self):
        try:
            import winreg
            key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
            app_name = self.Project.title + "Host"
            if getattr(sys, 'frozen', False):
                cmd = f'"{sys.executable}"'
            else:
                exe = sys.executable
                script = self.Project.p_project + "/" + self.Project.host_script
                cmd = f'"{exe}" "{script}"'
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_READ
            ) as key:
                try:
                    winreg.QueryValueEx(key, app_name)
                    return
                except FileNotFoundError:
                    pass
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE
            ) as key:
                winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ, cmd)
        except Exception:
            pass

    def unregister_startup(self):
        try:
            import winreg
            key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
            app_name = self.Project.title + "Host"
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE
            ) as key:
                winreg.DeleteValue(key, app_name)
        except Exception:
            pass
