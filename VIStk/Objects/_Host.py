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
from VIStk.Objects._TabManager import TabManager as _TabManager
from VIStk.Widgets._HostMenu import HostMenu
from VIStk.Widgets._InfoRow import InfoRow
from VIStk.Widgets._SplitView import SplitView

# Module-level singleton reference — set by Host.__init__, cleared on quit_host.
_HOST_INSTANCE: "Host | None" = None


def _ipc_port_file(project_title: str) -> str:
    safe = project_title.replace(" ", "_")
    return os.path.join(tempfile.gettempdir(), f"{safe}_vis_host.port")


def _parse_open_arg() -> "str | None":
    """Return the value of ``--open <name>`` from ``sys.argv``, or ``None``."""
    args = sys.argv[1:]
    try:
        idx = args.index("--open")
        return args[idx + 1]
    except (ValueError, IndexError):
        return None


class Host(Root):
    """Persistent application host that owns the Tk root window.

    All screen navigation routes through ``host.open()``.  Tabbed screens
    open as ``Frame``-based tabs inside the Host window.  Standalone screens
    spawn as Toplevels.

    Multiple instances of the same screen are supported: if a screen is
    already open anywhere (main window or any DetachedWindow), the new
    instance is labelled ``"Name (2)"``, ``"Name (3)"``, etc.

    Window title: ``project.title`` by default; ``"project: screen"`` when a
    tab is active; ``"project: screen \u2014 info"`` when the tab has a
    characteristic info string.

    Attributes:
        TabManager (TabManager): Property shim — returns the focused pane
            from the underlying ``SplitView``.
        HostMenu   (HostMenu)
        InfoRow    (InfoRow)
        fps        (float)
    """

    def __init__(self, start_hidden: bool = True, *args, **kwargs):
        global _HOST_INSTANCE
        super().__init__(*args, **kwargs)

        # Set baseline window title to the project name
        self.title(self.Project.title)

        self.protocol("WM_DELETE_WINDOW", self._hide_to_tray)

        self._split_view = SplitView(self, host=self)
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

        # Detached window tracking
        self._detached: list = []

        # FPS broadcast listeners — each DetachedWindow registers its InfoRow
        self._fps_listeners: list = []

        self.InfoRow = InfoRow(self, self.Project)
        self.InfoRow.pack(fill="x", side="bottom")

        self.HostMenu = HostMenu(self, quit_command=self.quit_host)
        self.HostMenu.attach()

        # FPS tracking
        self.fps: float = 0.0
        self._fps_last: float = time.time()
        self._fps_frames: int = 0
        self._fps_acc: float = 0.0

        self._call_queue: queue.SimpleQueue = queue.SimpleQueue()
        self._poll_main_queue()

        self._toplevels: dict[str, dict] = {}
        """name → {"window": Toplevel, "module": module | None, "hooks": module | None}"""

        # Multiple-instance tracking: base_name → count of currently open instances
        self._open_counts: dict[str, int] = {}

        self._tray_icon = None
        self._tray_thread: threading.Thread | None = None
        self._start_tray()

        self._ipc_server: socket.socket | None = None
        self._start_ipc()

        self._register_startup()

        _HOST_INSTANCE = self

        # If launched by Screen.load() on first boot, open the requested screen.
        _open_arg = _parse_open_arg()
        if _open_arg:
            start_hidden = False
            self.after(0, lambda: self.open(_open_arg))

        if start_hidden:
            self.withdraw()

    # ── Compatibility shim ─────────────────────────────────────────────────────

    @property
    def TabManager(self) -> "_TabManager":
        """Return the focused pane from the SplitView.

        Existing code that reads ``host.TabManager`` gets the pane the user
        last interacted with.  Methods that need *all* panes should use
        ``self._split_view`` directly.
        """
        return self._split_view.focused_pane

    # ── Navigation ─────────────────────────────────────────────────────────────

    def open(self, screen_name: str, stay_open: bool = False):
        """Unified navigation entry point."""
        scr = self.Project.getScreen(screen_name)
        if scr is None:
            return
        if scr.tabbed:
            self._open_tab(scr)
            self.deiconify()
        else:
            self._open_toplevel(scr)

    # ── Tabs ───────────────────────────────────────────────────────────────────

    def _get_all_tab_names(self) -> set[str]:
        """Return all display names currently open in any window."""
        names: set[str] = set(self._split_view.all_tabs().keys())
        for dw in self._detached:
            names.update(dw.tab_manager._tabs.keys())
        return names

    def _find_tab_by_base(self, base_name: str) -> tuple["_TabManager | None", "str | None"]:
        """Return (tab_manager, display_name) for the first open tab whose base_name matches.

        Searches all main-window panes first, then detached windows.
        Returns (None, None) if not found.
        """
        for pane in self._split_view.all_tab_managers():
            for display, entry in pane._tabs.items():
                if entry.get("base_name", display) == base_name:
                    return pane, display
        for dw in self._detached:
            for display, entry in dw.tab_manager._tabs.items():
                if entry.get("base_name", display) == base_name:
                    return dw.tab_manager, display
        return None, None

    def _unique_display_name(self, base: str) -> str:
        """Return a display name for *base* that doesn't conflict with open tabs."""
        existing = self._get_all_tab_names()
        if base not in existing:
            return base
        n = 2
        while f"{base} ({n})" in existing:
            n += 1
        return f"{base} ({n})"

    def _open_tab(self, scr):
        if scr.single_instance:
            tm, display = self._find_tab_by_base(scr.name)
            if tm is not None:
                tm.focus_tab(display)
                # If the tab lives in a detached window, bring that window forward
                for dw in self._detached:
                    if dw.tab_manager is tm:
                        try:
                            dw.win.deiconify()
                            dw.win.lift()
                            dw.win.focus_force()
                        except Exception:
                            pass
                        break
                return
        display = self._unique_display_name(scr.name)
        module  = self._import_screen(scr)
        hooks   = self._import_hooks(scr)
        icon    = self._load_tab_icon(scr)
        self.TabManager.open_tab(display, module, hooks=hooks, icon=icon,
                                 base_name=scr.name)

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

    def _on_tab_activate(self, name: str, module):
        self.HostMenu.clear_screen_items()
        self.HostMenu.reset_overrides()
        pane = self._split_view.find_pane_for_tab(name)
        if pane is None:
            return
        hooks = pane._tabs.get(name, {}).get("hooks")
        cfg = (getattr(hooks, "configure_menu", None)
               or getattr(module, "configure_menu", None))
        if cfg:
            try:
                cfg(self.HostMenu)
            except Exception:
                pass
        overrides = (getattr(hooks, "MENU_OVERRIDES", None)
                     or getattr(module, "MENU_OVERRIDES", None))
        if overrides:
            try:
                self.HostMenu.apply_overrides(overrides)
            except Exception:
                pass
        scr = self.Project.getScreen(
            pane._tabs.get(name, {}).get("base_name", name)
        )
        self.InfoRow.set_screen(name, str(scr.s_version) if scr else "")
        # Update window title (include info if already set)
        info = pane._tabs.get(name, {}).get("info", "")
        self._set_title(name, info)

    def _on_tab_deactivate(self, name: str | None):
        self.HostMenu.clear_screen_items()
        self.HostMenu.reset_overrides()
        self.InfoRow.set_screen("")
        if name is None:
            # All tabs closed — reset to project title
            self.title(self.Project.title)

    def _on_tab_info_change(self, name: str, info: str):
        """Triggered when a tab's characteristic info string changes."""
        pane = self._split_view.find_pane_for_tab(name)
        if pane is not None and pane is self._split_view.focused_pane and pane.active == name:
            self._set_title(name, info)

    def _set_title(self, screen: str, info: str = ""):
        base = self.Project.title
        if info:
            self.title(f"{base}: {screen} \u2014 {info}")
        else:
            self.title(f"{base}: {screen}")

    # ── Toplevels ──────────────────────────────────────────────────────────────

    def _open_toplevel(self, scr):
        if scr.name in self._toplevels:
            win = self._toplevels[scr.name]["window"]
            win.deiconify()
            win.lift()
            win.focus_force()
            return

        win = Toplevel(self)
        win.title(scr.name)

        module = self._import_screen(scr)
        hooks  = self._import_hooks(scr)
        if module and hasattr(module, "setup"):
            try:
                module.setup(win)
            except Exception:
                pass
            fn = getattr(hooks, "on_focused", None) or getattr(module, "on_focused", None)
            if fn:
                try:
                    fn()
                except Exception:
                    pass
        else:
            win.destroy()
            return

        self._toplevels[scr.name] = {"window": win, "module": module, "hooks": hooks}

        def _on_close():
            entry = self._toplevels.get(scr.name, {})
            mod  = entry.get("module")
            hks  = entry.get("hooks")
            fn = getattr(hks, "on_unfocused", None) or getattr(mod, "on_unfocused", None)
            if fn:
                try:
                    fn()
                except Exception:
                    pass
            win.destroy()
            self._toplevels.pop(scr.name, None)

        win.protocol("WM_DELETE_WINDOW", _on_close)

    def _close_screen(self, name: str):
        pane = self._split_view.find_pane_for_tab(name)
        if pane is not None:
            pane.close_tab(name)
        elif name in self._toplevels:
            self._close_toplevel(name)

    def _close_toplevel(self, name: str):
        entry = self._toplevels.get(name)
        if entry:
            entry["window"].protocol("WM_DELETE_WINDOW", lambda: None)
            mod = entry.get("module")
            hks = entry.get("hooks")
            fn = getattr(hks, "on_unfocused", None) or getattr(mod, "on_unfocused", None)
            if fn:
                try:
                    fn()
                except Exception:
                    pass
            entry["window"].destroy()
            self._toplevels.pop(name, None)

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
        name       = scr.name
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

    # ── Pop-out, detach, refresh ───────────────────────────────────────────────

    def _on_tab_popout(self, name: str):
        """Pop out via right-click — use current pointer position."""
        pane = self._split_view.find_pane_for_tab(name)
        if pane is None:
            return
        entry     = pane._tabs[name]
        module    = entry.get("module")
        hooks     = entry.get("hooks")
        icon      = entry.get("icon")
        base_name = entry.get("base_name", name)
        pane.close_tab(name)
        x = self.winfo_pointerx()
        y = self.winfo_pointery()
        self._open_detached(name, module, hooks, icon, base_name,
                            x, y, 0, 0)

    def _on_tab_detach(self, name: str):
        """Handle drag-to-detach — use pointer position and stored drag offsets."""
        pane = self._split_view.find_pane_for_tab(name)
        if pane is None:
            return
        entry     = pane._tabs[name]
        module    = entry.get("module")
        hooks     = entry.get("hooks")
        icon      = entry.get("icon")
        base_name = entry.get("base_name", name)
        bx = pane.tab_bar._last_drag_btn_offset_x
        by = pane.tab_bar._last_drag_btn_offset_y
        pane.close_tab(name)
        x = self.winfo_pointerx()
        y = self.winfo_pointery()
        self._open_detached(name, module, hooks, icon, base_name,
                            x, y, bx, by)

    def _on_tab_refresh(self, name: str):
        """Re-import and reopen the named tab at its current position."""
        pane = self._split_view.find_pane_for_tab(name)
        if pane is None:
            return
        entry     = pane._tabs[name]
        base_name = entry.get("base_name", name)
        icon      = entry.get("icon")
        idx       = pane.tab_bar.get_tab_idx(name)
        scr = self.Project.getScreen(base_name)
        if scr is None:
            pane.force_refresh_tab(name)
            return
        pane.close_tab(name)
        module = self._import_screen(scr)
        hooks  = self._import_hooks(scr)
        pane.open_tab(name, module, hooks=hooks, icon=icon,
                      insert_idx=idx, base_name=base_name)

    def _on_tab_split(self, name: str, direction: str):
        """Handle right-click 'Split right' / 'Split down'."""
        pane = self._split_view.find_pane_for_tab(name)
        if pane is None:
            return
        entry     = pane._tabs[name]
        module    = entry.get("module")
        hooks     = entry.get("hooks")
        icon      = entry.get("icon")
        base_name = entry.get("base_name", name)
        # Split transfers all tabs to left_pane; right_pane is empty
        left_pane, right_pane = self._split_view.split(pane, direction)
        # Move the clicked tab from left to right
        left_pane.close_tab(name)
        right_pane.open_tab(name, module, hooks=hooks, icon=icon,
                            base_name=base_name)

    def _open_detached(self, name: str, module, hooks, icon, base_name: str,
                       x_root: int, y_root: int,
                       btn_offset_x: int, btn_offset_y: int):
        """Create a DetachedWindow and position it under the cursor."""
        from VIStk.Objects._DetachedWindow import DetachedWindow
        dw = DetachedWindow(
            self, name, module, hooks, icon, base_name,
            x_root, y_root, btn_offset_x, btn_offset_y,
        )
        self._detached.append(dw)

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
            for listener in list(self._fps_listeners):
                try:
                    listener(self.fps)
                except Exception:
                    pass

    # ── Main-thread call queue ─────────────────────────────────────────────────

    def _poll_main_queue(self):
        try:
            while True:
                fn = self._call_queue.get_nowait()
                try:
                    fn()
                except Exception:
                    pass
        except queue.Empty:
            pass
        try:
            if self.winfo_exists():
                self.after(50, self._poll_main_queue)
        except Exception:
            pass

    # ── IPC server ─────────────────────────────────────────────────────────────

    def _start_ipc(self):
        try:
            srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            srv.bind(("127.0.0.1", 0))
            srv.listen(8)
            self._ipc_server = srv
            port = srv.getsockname()[1]
            with open(_ipc_port_file(self.Project.title), "w") as f:
                f.write(str(port))
            t = threading.Thread(target=self._ipc_listen, args=(srv,), daemon=True)
            t.start()
        except Exception:
            self._ipc_server = None

    def _ipc_listen(self, srv: socket.socket):
        while True:
            try:
                conn, _ = srv.accept()
                with conn:
                    data = conn.recv(1024).decode("utf-8", errors="ignore").strip()
                if data == "__VIS_QUIT__":
                    self._call_queue.put(self._do_quit)
                    break
                elif data.startswith("__VIS_CLOSE__:"):
                    n = data[len("__VIS_CLOSE__:"):]
                    self._call_queue.put(lambda name=n: self._close_screen(name))
                elif data:
                    self._call_queue.put(lambda name=data: self.open(name))
            except Exception:
                break

    def _stop_ipc(self):
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
        self.withdraw()

    def _restore(self, icon=None, item=None):
        self._call_queue.put(self._do_restore)

    def _do_restore(self):
        state = self.state()
        if state == "withdrawn":
            default = getattr(self.Project, "default_screen", None)
            if default:
                scr = self.Project.getScreen(default)
                if scr and scr.tabbed:
                    self._open_tab(scr)
            self.deiconify()
        elif state == "iconic":
            self.deiconify()
        self.lift()
        self.focus_force()

    # ── Startup registration ───────────────────────────────────────────────────

    def _register_startup(self):
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

    # ── Lifecycle ──────────────────────────────────────────────────────────────

    def quit_host(self, icon=None, item=None):
        if threading.current_thread() is not threading.main_thread():
            self._call_queue.put(self._do_quit)
            return
        self._do_quit()

    def _do_quit(self):
        global _HOST_INSTANCE
        self._stop_ipc()
        for name in list(self._toplevels.keys()):
            self._close_toplevel(name)
        for dw in list(self._detached):
            dw._on_close()
        for pane in self._split_view.all_tab_managers():
            for name in list(pane._tabs.keys()):
                pane.close_tab(name)
        if self._tray_icon:
            try:
                self._tray_icon.stop()
            except Exception:
                pass
            if self._tray_thread and self._tray_thread.is_alive():
                self._tray_thread.join(timeout=1.0)
        _HOST_INSTANCE = None
        super().unload()

    def unload(self):
        self._hide_to_tray()
