from __future__ import annotations

import getpass
import hashlib
import json
import queue
import socket
import sys
import threading
import time
from pathlib import Path
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

        self.Active: bool = True
        self.Project = Project()

        # When invoked as ``VIS <Project> <ScreenName>`` the screen name is
        # forwarded as ``sys.argv[1]`` (or ``argv[0]`` for a frozen Host
        # exe).  Resolve it (and any trailing CLI args) BEFORE creating any
        # Tk object, so the single-instance forward path can hand the
        # request to a running Host and exit without spinning up a root.
        self._startup_screen: str | None = self._resolve_startup_screen()
        self._startup_args: list[str] = self._resolve_startup_args()

        # Single-instance: a per-project/user localhost port is the mutex.
        # If another Host already holds it, forward our open request to it
        # and go inert — the entry script's ``while host.Active`` loop sees
        # ``Active == False`` and exits without showing a window.
        self._lock_sock: socket.socket | None = None
        self._listener_thread: threading.Thread | None = None
        self._ipc_queue: queue.SimpleQueue = queue.SimpleQueue()
        self._lock_port: int = self._compute_lock_port()
        if not self._acquire_lock():
            self._forward_to_primary(self._startup_screen, self._startup_args)
            self.Active = False
            _HOST_INSTANCE = self
            return

        self.root = Tk()
        self.root.withdraw()

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

        self._opened_default = False

        _HOST_INSTANCE = self

        # We hold the lock — start accepting forwarded requests from
        # later launches.
        self._start_ipc_listener()

    def _resolve_startup_screen(self) -> str | None:
        """Return the screen name passed on the command line, or None.

        Walks ``sys.argv[1:]`` (Python skips ``argv[0]`` = script path in
        dev mode; frozen builds get the exe path as ``argv[0]``).  Only
        returns a name that matches a registered screen — unknown args
        fall through and the project's ``default_screen`` is used.
        """
        for arg in sys.argv[1:]:
            if arg.startswith("-"):
                continue
            # Ignore the host script path itself if it appears in argv
            if arg.endswith(".py") and Path(arg).name.lower() == "host.py":
                continue
            if self.Project.getScreen(arg) is not None:
                return arg
        return None

    def _resolve_startup_args(self) -> list[str]:
        """CLI args to forward alongside the startup screen.

        Everything in ``sys.argv[1:]`` except the host script path and
        the resolved startup screen name — i.e. the ``--Flag value``
        pairs a screen's ``ArgHandler`` would consume.  Captured here so
        the single-instance forward path can hand them to the running
        Host along with the screen name.
        """
        out: list[str] = []
        for arg in sys.argv[1:]:
            if arg.endswith(".py") and Path(arg).name.lower() == "host.py":
                continue
            if arg == self._startup_screen:
                continue
            out.append(arg)
        return out

    # ── Single instance (localhost socket mutex + open-request forwarding) ──────
    #
    # Binding a per-project/user localhost port IS the mutex: only one
    # process can hold it.  The holder is the primary Host and listens for
    # forwarded open requests; a second launch fails to bind, forwards its
    # request to the holder, and exits.  127.0.0.1-only, args-only payload
    # — see module docstring rationale in the commit that introduced this.

    _LOCK_PORT_LOW = 49152    # IANA dynamic/private range
    _LOCK_PORT_HIGH = 65535
    _LOCK_CONNECT_TIMEOUT = 0.5

    def _compute_lock_port(self) -> int:
        """Stable port from project title + OS user.

        Same inputs → same port, so the primary and a later forwarder
        independently agree where to talk without a shared file.  Keyed
        by user so two accounts on one machine each run their own Host.
        """
        try:
            user = getpass.getuser()
        except Exception:
            user = ""
        key = f"{self.Project.title}\x00{user}".encode("utf-8")
        h = int.from_bytes(hashlib.sha256(key).digest()[:4], "big")
        span = self._LOCK_PORT_HIGH - self._LOCK_PORT_LOW
        return self._LOCK_PORT_LOW + (h % span)

    def _acquire_lock(self) -> bool:
        """Try to bind the lock port.  True → we're the primary Host.

        On POSIX we set ``SO_REUSEADDR`` to dodge ``TIME_WAIT`` bind
        failures on quick restart (it does NOT permit a second live
        binder).  On Windows we leave the default exclusive bind —
        ``SO_REUSEADDR`` there WOULD let a second process bind and break
        the mutex, so it must not be set.
        """
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        if sys.platform != "win32":
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("127.0.0.1", self._lock_port))
            sock.listen(8)
        except OSError:
            sock.close()
            return False
        self._lock_sock = sock
        return True

    def _forward_to_primary(self, screen_name: str | None,
                            args: list[str] | None = None) -> bool:
        """Send an open request to the running Host.  True if delivered.

        Best-effort: a False return (primary died between our failed bind
        and this connect) leaves the caller inert.  The user relaunches.
        """
        payload = json.dumps({
            "screen": screen_name,
            "args": list(args or []),
        }).encode("utf-8")
        try:
            with socket.create_connection(
                ("127.0.0.1", self._lock_port),
                timeout=self._LOCK_CONNECT_TIMEOUT,
            ) as sock:
                sock.sendall(len(payload).to_bytes(4, "big") + payload)
            return True
        except OSError:
            return False

    def _start_ipc_listener(self) -> None:
        """Spawn the daemon thread that accepts forwarded requests."""
        if self._lock_sock is None:
            return
        self._listener_thread = threading.Thread(
            target=self._ipc_accept_loop, daemon=True,
            name=f"VIStk-Host-IPC-{self.Project.title}",
        )
        self._listener_thread.start()

    def _ipc_accept_loop(self) -> None:
        """Accept connections, parse one request each, queue for the main
        loop.  Runs on a background thread — does NOT touch Tk; it only
        puts onto ``_ipc_queue``, which :meth:`update` drains."""
        while self._lock_sock is not None:
            try:
                conn, _addr = self._lock_sock.accept()
            except OSError:
                break  # socket closed during shutdown
            with conn:
                try:
                    raw_len = self._recv_exact(conn, 4)
                    if raw_len is None:
                        continue
                    length = int.from_bytes(raw_len, "big")
                    # Payloads are tiny JSON; cap to reject junk/hostile.
                    if length <= 0 or length > 64 * 1024:
                        continue
                    data = self._recv_exact(conn, length)
                    if data is None:
                        continue
                    msg = json.loads(data.decode("utf-8"))
                except Exception:
                    continue
                self._ipc_queue.put((msg.get("screen"), msg.get("args") or []))

    @staticmethod
    def _recv_exact(conn: socket.socket, n: int) -> bytes | None:
        """Read exactly *n* bytes from *conn*, or None if it closed early."""
        buf = b""
        while len(buf) < n:
            chunk = conn.recv(n - len(buf))
            if not chunk:
                return None
            buf += chunk
        return buf

    def _drain_ipc_queue(self) -> None:
        """Process forwarded open requests on the Tk main loop.

        Called from :meth:`update`.  Opening a screen and touching
        windows must happen on the main thread, hence the queue handoff
        from the listener thread.
        """
        try:
            while True:
                screen_name, args = self._ipc_queue.get_nowait()
                if screen_name:
                    self.open(screen_name, args)
                # Surface the running app: a relaunch should bring a
                # window forward, not silently no-op.
                self._raise_a_window()
        except queue.Empty:
            pass

    def _raise_a_window(self) -> None:
        """Bring the most recent DetachedWindow to the foreground."""
        if not self.detached_windows:
            return
        dw = self.detached_windows[-1]
        try:
            dw.win.deiconify()
            dw.win.lift()
            dw.win.focus_force()
        except Exception:
            pass

    def _close_lock(self) -> None:
        """Close the listener socket, unblocking the accept loop."""
        sock = self._lock_sock
        self._lock_sock = None
        if sock is not None:
            try:
                sock.close()
            except Exception:
                pass

    # ── Navigation ─────────────────────────────────────────────────────────────

    def open(self, screen_name: str, args: list | None = None):
        """Unified navigation entry point.

        Tabbed screens open as tabs in the active TabManager's window.
        Standalone (tabbed=False) screens open as new DetachedWindows.
        When running from a compiled installation, refuses to open a
        screen whose binary is not present on disk and shows an inline
        banner in the active window's InfoRow instead.

        *args* are CLI-style arguments forwarded from the command line
        (``WOM.exe <Screen> --Flag value``) or a single-instance IPC
        request; they reach the screen's ``ArgHandler`` before its
        ``setup()`` runs.
        """
        scr = self.Project.getScreen(screen_name)
        if scr is None:
            return
        if not self._check_installed(scr):
            return
        if scr.tabbed:
            self._open_tab(scr, args)
        else:
            self._open_standalone(scr, args)

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

    def _open_tab(self, scr, args: list | None = None):
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
        icon = self._load_tab_icon(scr)

        # Open in the active TabManager, or the first window's primary pane
        target = self.active_tab_manager
        if target is None and self.detached_windows:
            target = self.detached_windows[0].tab_manager
        if target is None:
            # No window exists yet — create one; it opens the tab itself.
            from VIStk.Objects._DetachedWindow import DetachedWindow
            dw = DetachedWindow(self, scr, args=args)
            return

        target.open_screen(scr, display, icon=icon, args=args)

    def _open_standalone(self, scr, args: list | None = None):
        """Open a standalone (tabbed=False) screen as a new DetachedWindow.

        Standalone windows are chromeless: the tab bar is hidden and the
        window adopts the screen's own icon and name, so a screen with
        ``tabbed=False`` looks like a plain application window rather than
        a single-tab Host shell.
        """
        from VIStk.Objects._DetachedWindow import DetachedWindow
        dw = DetachedWindow(self, scr, chromeless=True, args=args)

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

    # ── Per-screen loop tick ──────────────────────────────────────────────────

    def _tick_screens(self):
        """Call ``loop()`` on every open tab's screen module (#117).

        Iterates each ``TabManager`` (main window + all DetachedWindows)
        and invokes the module-level ``loop()`` function on every open
        tab whose module defines one.

        Runs on every ``Host.update()`` call -- not on a ``tk.after``
        timer -- so screens get the same per-frame cadence in the Host
        that they get in the standalone driver.  Throttling here would
        be inventing a frame-rate cap that the standalone path does not
        impose; if a screen wants to throttle, it can do so inside its
        own ``loop()``.
        """
        for tm in list(self.registered_tab_managers):
            for entry in tm._tabs.values():
                module = entry.get("module")
                loop = getattr(module, "loop", None)
                if callable(loop):
                    try:
                        loop()
                    except Exception:
                        import traceback
                        traceback.print_exc()

    def update(self):
        """Process all pending Tk events for the root and its Toplevels.

        On the first call, opens the startup screen so that Host.py has
        time to configure ``default_menu_setup`` before any window is created.
        Prefers the screen passed on the command line (``VIS <Project>
        <ScreenName>``) and falls back to ``Project.default_screen``.
        """
        if not self._opened_default:
            self._opened_default = True
            startup = self._startup_screen or self.Project.default_screen
            if startup:
                # Forward CLI args only when the startup screen is the one
                # named on the command line — not when falling back to the
                # project default (the args weren't meant for it).
                startup_args = (self._startup_args
                                if startup == self._startup_screen else None)
                self.open(startup, startup_args)
        self._drain_ipc_queue()
        self._tick_screens()
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
        self._close_lock()
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
