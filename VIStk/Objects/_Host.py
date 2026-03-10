from __future__ import annotations

import importlib
import importlib.util
import subprocess
import sys
import threading
import time
import winreg
from tkinter import Frame

from VIStk.Objects._Root import Root
from VIStk.Widgets._TabBar import TabBar
from VIStk.Widgets._HostMenu import HostMenu

# Module-level singleton reference — set by Host.__init__, cleared on unload.
# Project.open() checks this to decide whether to route through the Host.
_HOST_INSTANCE: "Host | None" = None


class Host(Root):
    """Persistent application host that owns the Tk root window.

    The Host never closes; pressing the window close button hides it to the
    system tray.  All screen navigation routes through ``host.open()``.

    Tabbed screens open as ``Frame``-based tabs inside the Host window.
    Standalone screens are spawned as subprocesses via ``subprocess.Popen``.

    Attributes:
        TabBar (TabBar): The tab bar widget at the top of the window.
        HostMenu (HostMenu): The persistent menu bar.
        fps (float): Frames per second tracked by the update loop.
    """

    def __init__(self, *args, **kwargs):
        global _HOST_INSTANCE
        super().__init__(*args, **kwargs)

        # Override the close-window protocol to hide rather than destroy.
        self.protocol("WM_DELETE_WINDOW", self._hide_to_tray)

        # Tab management
        self._tabs: dict[str, dict] = {}
        """name → {"frame": Frame, "module": module | None}"""
        self._content_frame = Frame(self)
        self._content_frame.place(relx=0, rely=0, relwidth=1, relheight=1)

        # Widgets
        self.TabBar = TabBar(self)
        self.TabBar.place(relx=0, rely=0, relwidth=1, relheight=0.05)
        self._content_frame.place(relx=0, rely=0.05, relwidth=1, relheight=0.95)

        self.TabBar.on_focus_change = self._on_tab_focus_change
        self.TabBar.on_tab_close = self._on_tab_close_request

        self.HostMenu = HostMenu(self, quit_command=self.quit_host)
        self.HostMenu.attach()

        # FPS tracking
        self.fps: float = 0.0
        self._fps_last: float = time.time()
        self._fps_frames: int = 0
        self._fps_acc: float = 0.0

        # System tray (pystray) — initialised lazily so missing dependency
        # only fails when actually needed.
        self._tray_icon = None
        self._tray_thread: threading.Thread | None = None
        self._start_tray()

        # OS startup registration (Windows only)
        self._register_startup()

        # Register singleton
        _HOST_INSTANCE = self

    # ── Navigation ─────────────────────────────────────────────────────────────

    def open(self, screen_name: str, stay_open: bool = False):
        """Unified navigation entry point.

        * Tabbed screen → open or focus its tab.
        * Standalone screen → spawn as subprocess.  If ``stay_open`` is
          ``False`` the caller should close after this returns.

        Args:
            screen_name: Name of the target screen in ``project.json``.
            stay_open: When ``True``, the calling screen is kept open after
                launching a standalone target.  Has no effect for tabbed screens.
        """
        scr = self.Project.getScreen(screen_name)
        if scr is None:
            return

        if scr.tabbed:
            self._open_tab(scr)
            self.deiconify()
        else:
            subprocess.Popen([sys.executable, self.Project.p_project + "/" + scr.script])

    # ── Tabs ───────────────────────────────────────────────────────────────────

    def _open_tab(self, scr):
        if self.TabBar.has_tab(scr.name):
            self.TabBar.focus_tab(scr.name)
            return

        frame = Frame(self._content_frame)
        frame.place(relx=0, rely=0, relwidth=1, relheight=1)

        # Try to import and call the screen's setup() hook
        module = self._import_screen(scr)
        if module and hasattr(module, "setup"):
            try:
                module.setup(frame)
            except Exception:
                pass

        self._tabs[scr.name] = {"frame": frame, "module": module}
        self.TabBar.open_tab(scr.name)

    def _on_tab_focus_change(self, name: str | None):
        # Hide all content frames, show the active one
        for tab_name, tab in self._tabs.items():
            if tab_name == name:
                tab["frame"].lift()
            else:
                tab["frame"].lower()
                mod = tab.get("module")
                if mod and hasattr(mod, "on_deactivate"):
                    try:
                        mod.on_deactivate()
                    except Exception:
                        pass

        if name and name in self._tabs:
            mod = self._tabs[name].get("module")
            if mod and hasattr(mod, "on_activate"):
                try:
                    mod.on_activate()
                except Exception:
                    pass
            # Swap screen-contributed menu items
            if mod and hasattr(mod, "configure_menu"):
                try:
                    items = mod.configure_menu(self.HostMenu.menubar)
                    if items:
                        self.HostMenu.set_screen_items(items, label=name)
                    else:
                        self.HostMenu.clear_screen_items()
                except Exception:
                    self.HostMenu.clear_screen_items()
            else:
                self.HostMenu.clear_screen_items()

    def _on_tab_close_request(self, name: str):
        if name in self._tabs:
            mod = self._tabs[name].get("module")
            if mod and hasattr(mod, "on_deactivate"):
                try:
                    mod.on_deactivate()
                except Exception:
                    pass
            self._tabs[name]["frame"].destroy()
            del self._tabs[name]
        self.HostMenu.clear_screen_items()

    # ── Screen import ──────────────────────────────────────────────────────────

    def _import_screen(self, scr):
        """Dynamically import a screen module so setup() can be called."""
        script_path = self.Project.p_project + "/" + scr.script
        try:
            spec = importlib.util.spec_from_file_location(scr.name, script_path)
            if spec is None:
                return None
            mod = importlib.util.module_from_spec(spec)
            # Guard: don't execute top-level code (requires __main__ guard in screen)
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

    # ── Tray ───────────────────────────────────────────────────────────────────

    def _start_tray(self):
        try:
            import pystray
            import PIL.Image
            import PIL.ImageDraw

            icon_path = self.Project.p_icons
            import glob as _glob
            matches = _glob.glob(icon_path + "/" + self.Project.d_icon + ".*")
            if matches:
                img = PIL.Image.open(matches[0])
            else:
                # Fallback: tiny blank icon
                img = PIL.Image.new("RGB", (16, 16), color=(80, 80, 200))
                draw = PIL.ImageDraw.Draw(img)
                draw.rectangle([4, 4, 12, 12], fill=(255, 255, 255))

            menu = pystray.Menu(
                pystray.MenuItem("Show", self._restore),
                pystray.MenuItem("Quit", self.quit_host),
            )
            self._tray_icon = pystray.Icon(
                self.Project.title, img, self.Project.title, menu
            )

            self._tray_thread = threading.Thread(
                target=self._tray_icon.run, daemon=True
            )
            self._tray_thread.start()
        except Exception:
            # pystray unavailable — tray silently disabled
            self._tray_icon = None

    def _hide_to_tray(self):
        """Hide the window without destroying it."""
        self.withdraw()

    def _restore(self, icon=None, item=None):
        """Restore the window from the tray."""
        self.deiconify()

    # ── Startup registration ───────────────────────────────────────────────────

    def _register_startup(self):
        """Register the Host in the Windows startup registry (first run)."""
        try:
            key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
            app_name = self.Project.title + "Host"
            exe = sys.executable
            script = self.Project.p_project + "/Host.py"
            cmd = f'"{exe}" "{script}"'

            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_READ
            ) as key:
                try:
                    winreg.QueryValueEx(key, app_name)
                    return  # Already registered
                except FileNotFoundError:
                    pass

            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE
            ) as key:
                winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ, cmd)
        except Exception:
            pass

    def unregister_startup(self):
        """Remove the Host from the Windows startup registry."""
        try:
            key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
            app_name = self.Project.title + "Host"
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE
            ) as key:
                winreg.DeleteValue(key, app_name)
        except Exception:
            pass

    # ── Lifecycle ──────────────────────────────────────────────────────────────

    def quit_host(self, icon=None, item=None):
        """Fully shut down the Host (called from tray Quit or programmatically)."""
        global _HOST_INSTANCE
        if self._tray_icon:
            try:
                self._tray_icon.stop()
            except Exception:
                pass
        _HOST_INSTANCE = None
        super().unload()

    def unload(self):
        """Override: hide to tray instead of destroying."""
        self._hide_to_tray()
