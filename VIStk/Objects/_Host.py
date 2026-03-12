from __future__ import annotations

import importlib
import importlib.util
import os
import queue
import socket
import sys
import tempfile
import threading
import time
from tkinter import Toplevel

from VIStk.Objects._Root import Root
from VIStk.Objects._TabManager import TabManager
from VIStk.Widgets._HostMenu import HostMenu
from VIStk.Widgets._InfoRow import InfoRow

# Module-level singleton reference — set by Host.__init__, cleared on quit_host.
# Project.open() checks this to decide whether to route through the Host.
_HOST_INSTANCE: "Host | None" = None


def _ipc_port_file(project_title: str) -> str:
    """Return the path of the temp file that stores the Host's IPC port."""
    safe = project_title.replace(" ", "_")
    return os.path.join(tempfile.gettempdir(), f"{safe}_vis_host.port")


class Host(Root):
    """Persistent application host that owns the Tk root window.

    The Host never closes on its own; pressing the window close button hides it
    to the system tray.  It starts hidden by default and appears when the user
    clicks the tray icon (which also opens the default screen).

    All screen navigation routes through ``host.open()``.  Tabbed screens open
    as ``Frame``-based tabs inside the Host window.  Standalone screens are
    spawned as subprocesses via ``subprocess.Popen``.

    An IPC server (localhost TCP) lets other scripts request screen opens via
    ``send_to_host(project_title, screen_name)``.

    Attributes:
        TabManager (TabManager): Owns the tab strip and content area.
        HostMenu (HostMenu): The persistent menu bar.
        fps (float): Frames per second tracked by the update loop.
    """

    def __init__(self, start_hidden: bool = True, *args, **kwargs):
        global _HOST_INSTANCE
        super().__init__(*args, **kwargs)

        # Override the close-window protocol to hide rather than destroy.
        self.protocol("WM_DELETE_WINDOW", self._hide_to_tray)

        # TabManager owns the tab strip and all screen content frames
        self.TabManager = TabManager(self)
        self.TabManager.pack(fill="both", expand=True)
        self.TabManager.on_tab_activate = self._on_tab_activate
        self.TabManager.on_tab_deactivate = self._on_tab_deactivate

        # InfoRow status bar sits below the TabManager
        self.InfoRow = InfoRow(self, self.Project)
        self.InfoRow.pack(fill="x", side="bottom")

        self.HostMenu = HostMenu(self, quit_command=self.quit_host)
        self.HostMenu.attach()

        # FPS tracking
        self.fps: float = 0.0
        self._fps_last: float = time.time()
        self._fps_frames: int = 0
        self._fps_acc: float = 0.0

        # Thread-safe call queue: non-main threads (pystray, IPC) put callables
        # here; the main thread drains it via _poll_main_queue() / after().
        # self.after() must NOT be called from non-main threads.
        self._call_queue: queue.SimpleQueue = queue.SimpleQueue()
        self._poll_main_queue()

        # TopLevel tracking for non-tabbed screens opened by the Host
        self._toplevels: dict[str, dict] = {}
        """name → {"window": Toplevel, "module": module | None}"""

        # System tray — start before hiding so the icon is ready
        self._tray_icon = None
        self._tray_thread: threading.Thread | None = None
        self._start_tray()

        # IPC server — lets parallel scripts request screen opens
        self._ipc_server: socket.socket | None = None
        self._start_ipc()

        # OS startup registration (Windows only)
        self._register_startup()

        # Register singleton
        _HOST_INSTANCE = self

        # Start hidden in tray by default
        if start_hidden:
            self.withdraw()

    # ── Navigation ─────────────────────────────────────────────────────────────

    def open(self, screen_name: str, stay_open: bool = False):
        """Unified navigation entry point.

        * Tabbed screen → open or focus its tab in the Host window.
        * Non-tabbed screen → open or focus a Toplevel window.

        Args:
            screen_name: Name of the target screen in ``project.json``.
            stay_open: Kept for API compatibility; unused when Host is running.
        """
        scr = self.Project.getScreen(screen_name)
        if scr is None:
            return

        if scr.tabbed:
            self._open_tab(scr)
            self.deiconify()
        else:
            self._open_toplevel(scr)

    # ── Tabs ───────────────────────────────────────────────────────────────────

    def _open_tab(self, scr):
        """Import the screen and hand it off to TabManager."""
        module = self._import_screen(scr)
        icon = self._load_tab_icon(scr)
        self.TabManager.open_tab(scr.name, module, icon=icon)

    def _load_tab_icon(self, scr) -> "PIL.ImageTk.PhotoImage | None":
        """Load a 16x16 PhotoImage for *scr*'s icon, or None if unavailable."""
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

    def _on_tab_activate(self, name: str, module):
        """Called by TabManager when a tab gains focus."""
        if module and hasattr(module, "configure_menu"):
            try:
                module.configure_menu(self.HostMenu)
            except Exception:
                pass
        scr = self.Project.getScreen(name)
        self.InfoRow.set_screen(name, str(scr.s_version) if scr else "")

    def _on_tab_deactivate(self, name: str | None):
        """Called by TabManager when a tab loses focus (or all tabs close)."""
        self.HostMenu.clear_screen_items()
        self.InfoRow.set_screen("")

    # ── Toplevels ──────────────────────────────────────────────────────────────

    def _open_toplevel(self, scr):
        """Open a non-tabbed screen in a Toplevel window managed by the Host."""
        if scr.name in self._toplevels:
            # Already open — bring to front
            win = self._toplevels[scr.name]["window"]
            win.deiconify()
            win.lift()
            win.focus_force()
            return

        win = Toplevel(self)
        win.title(scr.name)

        module = self._import_screen(scr)
        if module and hasattr(module, "setup"):
            try:
                module.setup(win)
            except Exception:
                pass
            if hasattr(module, "on_activate"):
                try:
                    module.on_activate()
                except Exception:
                    pass
        else:
            win.destroy()
            return

        self._toplevels[scr.name] = {"window": win, "module": module}

        def _on_close():
            mod = self._toplevels.get(scr.name, {}).get("module")
            if mod and hasattr(mod, "on_deactivate"):
                try:
                    mod.on_deactivate()
                except Exception:
                    pass
            win.destroy()
            self._toplevels.pop(scr.name, None)

        win.protocol("WM_DELETE_WINDOW", _on_close)

    def _close_screen(self, name: str):
        """Close a screen managed by the Host — tab or Toplevel."""
        if self.TabManager.has_tab(name):
            self.TabManager.close_tab(name)
        elif name in self._toplevels:
            self._close_toplevel(name)

    def _close_toplevel(self, name: str):
        """Close a managed Toplevel by screen name."""
        entry = self._toplevels.get(name)
        if entry:
            entry["window"].protocol("WM_DELETE_WINDOW", lambda: None)
            mod = entry.get("module")
            if mod and hasattr(mod, "on_deactivate"):
                try:
                    mod.on_deactivate()
                except Exception:
                    pass
            entry["window"].destroy()
            self._toplevels.pop(name, None)

    # ── Screen import ──────────────────────────────────────────────────────────

    def _import_screen(self, scr):
        """Dynamically import a screen module so setup() can be called.

        Ensures the project directory is on ``sys.path`` so that relative
        package imports inside the screen (``Screens.*``, ``modules.*``) resolve.
        """
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
            self.InfoRow.set_fps(self.fps)

    # ── Main-thread call queue ─────────────────────────────────────────────────

    def _poll_main_queue(self):
        """Drain the cross-thread call queue on the main thread.

        Called once at startup and reschedules itself via ``after()``.
        Only this method (running on the main thread) ever calls ``after()``,
        which makes it safe regardless of what other threads are doing.
        """
        try:
            while True:
                fn = self._call_queue.get_nowait()
                try:
                    fn()
                except Exception:
                    pass
        except queue.Empty:
            pass
        self.after(50, self._poll_main_queue)

    # ── IPC server ─────────────────────────────────────────────────────────────

    def _start_ipc(self):
        """Bind a localhost TCP server and write the port to a temp file."""
        try:
            srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            srv.bind(("127.0.0.1", 0))
            srv.listen(8)
            self._ipc_server = srv
            port = srv.getsockname()[1]

            port_file = _ipc_port_file(self.Project.title)
            with open(port_file, "w") as f:
                f.write(str(port))

            t = threading.Thread(target=self._ipc_listen, args=(srv,), daemon=True)
            t.start()
        except Exception:
            self._ipc_server = None

    def _ipc_listen(self, srv: socket.socket):
        """Accept connections and dispatch IPC messages on the main thread.

        Reserved control messages start with ``__VIS_``:

        * ``__VIS_QUIT__`` — gracefully shut down the Host.

        Any other message is treated as a screen name to open.
        """
        while True:
            try:
                conn, _ = srv.accept()
                with conn:
                    data = conn.recv(1024).decode("utf-8", errors="ignore").strip()
                if data == "__VIS_QUIT__":
                    self._call_queue.put(self._do_quit)
                    break
                elif data.startswith("__VIS_CLOSE__:"):
                    name = data[len("__VIS_CLOSE__:"):]
                    self._call_queue.put(lambda n=name: self._close_screen(n))
                elif data:
                    self._call_queue.put(lambda name=data: self.open(name))
            except Exception:
                break

    def _stop_ipc(self):
        """Close the IPC server socket and remove the port file."""
        if self._ipc_server:
            try:
                self._ipc_server.close()
            except Exception:
                pass
            self._ipc_server = None
        try:
            os.remove(_ipc_port_file(self.Project.title))
        except Exception:
            pass

    # ── Tray ───────────────────────────────────────────────────────────────────

    def _start_tray(self):
        try:
            import pystray
            import PIL.Image
            import PIL.ImageDraw
            import glob as _glob

            matches = _glob.glob(
                self.Project.p_icons + "/" + self.Project.d_icon + ".*"
            )
            if matches:
                img = PIL.Image.open(matches[0])
            else:
                img = PIL.Image.new("RGB", (16, 16), color=(80, 80, 200))
                draw = PIL.ImageDraw.Draw(img)
                draw.rectangle([4, 4, 12, 12], fill=(255, 255, 255))

            menu = pystray.Menu(
                pystray.MenuItem("Show", self._restore, default=True),
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
            self._tray_icon = None

    def _hide_to_tray(self):
        """Hide the window without destroying it."""
        self.withdraw()

    def _restore(self, icon=None, item=None):
        """Restore the window from the tray and open the default screen."""
        # Called from the pystray thread — route via the call queue (thread-safe).
        self._call_queue.put(self._do_restore)

    def _do_restore(self):
        """Main-thread restore: open default screen when hidden; focus when visible."""
        state = self.state()
        if state == "withdrawn":
            # Hidden to tray — open the default screen (if tabbed) then show
            default = getattr(self.Project, "default_screen", None)
            if default:
                scr = self.Project.getScreen(default)
                if scr and scr.tabbed:
                    self._open_tab(scr)
            self.deiconify()
        elif state == "iconic":
            # OS-minimised via taskbar — just restore
            self.deiconify()
        # Always bring to front
        self.lift()
        self.focus_force()

    # ── Startup registration ───────────────────────────────────────────────────

    def _register_startup(self):
        """Register the Host in the Windows startup registry (first run only)."""
        try:
            import winreg
            key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
            app_name = self.Project.title + "Host"
            exe = sys.executable
            script = self.Project.p_project + "/" + self.Project.host_script
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
            import winreg
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
        """Fully shut down the Host (called from tray Quit or programmatically).

        Safe to call from any thread.
        """
        # If called from a non-main thread (pystray, IPC), route via the queue.
        if threading.current_thread() is not threading.main_thread():
            self._call_queue.put(self._do_quit)
            return
        self._do_quit()

    def _do_quit(self):
        """Perform the actual shutdown sequence — must run on the main thread."""
        global _HOST_INSTANCE
        self._stop_ipc()

        # Run deactivation hooks and close all managed screens before destroying
        for name in list(self._toplevels.keys()):
            self._close_toplevel(name)
        for name in list(self.TabManager._tabs.keys()):
            self.TabManager.close_tab(name)

        if self._tray_icon:
            try:
                self._tray_icon.stop()
            except Exception:
                pass
            # Give pystray's thread a moment to remove the tray icon.
            if self._tray_thread and self._tray_thread.is_alive():
                self._tray_thread.join(timeout=1.0)
        _HOST_INSTANCE = None
        super().unload()

    def unload(self):
        """Override: hide to tray instead of destroying."""
        self._hide_to_tray()
