from __future__ import annotations

import getpass
import hashlib
import json
import os
import queue
import socket
import sys
import threading
import time
from pathlib import Path
from tkinter import Tk

from VIStk.Structures._Project import Project
from VIStk.Structures._VINFO import is_compiled

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
        self._startup_screen, self._startup_args = self._resolve_startup()

        # ``--help`` / ``-h`` is pure terminal output (the full command listing
        # for a bare ``--help``, or one command's long help) — it needs no
        # Host, lock, or daemonize, so handle it first and go inert.
        _help_token, _, _help_flag = self._cli_tokens()
        if _help_flag:
            print(self._cli_help_text(_help_token))
            self.Active = False
            _HOST_INSTANCE = self
            return

        # Host-level CLI commands are discovered lazily from the project's
        # ``commands`` package (``commands/c_<name>.py`` -> ``_c_<name>``) when
        # a CLI invocation is resolved below -- see :meth:`_run_cli_client`.

        # POSIX: a process launched from a terminal holds that terminal for
        # its whole life (there is no Windows-style GUI subsystem).  A GUI
        # launch should free the shell immediately, so daemonize (fork +
        # setsid) before any threads or Tk exist.  CLI commands stay in the
        # foreground so their stdio works and the shell waits — the Linux
        # mirror of the console ``.com`` (#152).
        if sys.platform != "win32" and not self._is_cli_invocation():
            self._daemonize()

        # Single-instance: a per-project/user localhost port is the mutex.
        # If another Host already holds it we are a secondary launch.  A GUI
        # request (a screen name, or no args = bring-to-front) is forwarded
        # and we go inert.  A CLI request (args that resolve to a Host-level
        # command, no screen) runs a continuation-passing exchange with the
        # running Host, prints its result here, then goes inert.  Either way
        # the entry script's ``while host.Active`` loop sees ``Active == False``
        # and exits without showing a window.
        self._lock_sock: socket.socket | None = None
        self._listener_thread: threading.Thread | None = None
        self._ipc_queue: queue.SimpleQueue = queue.SimpleQueue()
        self._lock_port: int = self._compute_lock_port()
        if not self._acquire_lock():
            if self._is_cli_invocation():
                self._run_cli_client()
            elif self._startup_screen and self._resolve_command(self._startup_screen):
                # Screen with a c_<Screen>.py intercept: run _c_<Screen> on the
                # running Host, which transforms/validates the args and opens
                # the screen, or returns a terminal-side CLI response.
                self._cli_exchange((self._run_screen_intercept,
                                    (self._startup_screen, self._startup_args)))
            else:
                self._forward_to_primary(self._startup_screen, self._startup_args)
            self.Active = False
            _HOST_INSTANCE = self
            return

        # We hold the lock → no Host was running.  A console command must
        # still RUN, but must NEVER spin up the GUI as a side effect of
        # being the first instance.  Run the command's continuation chain
        # in-process (no Tk, no socket) and go inert, releasing the lock.
        # _HOST_INSTANCE is left None so commands see "no live Host" and
        # degrade gracefully (e.g. ping reports open_windows=0) rather than
        # touching this half-built instance.  An unknown command still
        # reports a usage error.
        if self._is_cli_invocation():
            cmd = self._startup_args[0].lower()
            entry = self._resolve_command(cmd)
            if entry is None:
                self._cli_usage_error(cmd)
            else:
                self._cli_run_local((entry, (self._startup_args[1:],)))
            self._close_lock()
            self.Active = False
            return

        # Screen with a c_<Screen>.py intercept, no Host running: run the
        # intercept in-process before becoming the GUI Host.  A (callable,
        # args) return is a terminal-side CLI response — run it and stay
        # headless (don't open a window); a list transforms the launch args;
        # None keeps the original args.  The GUI then opens _startup_screen
        # with _startup_args on its first update().
        if self._startup_screen:
            _icept = self._resolve_command(self._startup_screen)
            if _icept is not None:
                try:
                    _res = _icept(list(self._startup_args))
                except Exception:
                    import traceback
                    traceback.print_exc()
                    _res = None
                if isinstance(_res, tuple):
                    self._cli_run_local(_res)
                    self._close_lock()
                    self.Active = False
                    return
                if isinstance(_res, list):
                    self._startup_args = _res

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

    def _resolve_startup(self) -> tuple:
        """Resolve the launch into ``(startup_screen, startup_args)``.

        The first non-flag word is the command/screen token, resolved through
        the CLI registry so aliases work (a screen alias launches its screen,
        a command alias runs its command):

          * token is a **screen** (or screen alias) → ``(name, args)`` — a GUI
            launch/forward; the screen's ``ArgHandler`` consumes ``args``.
          * token is a **command** (or command alias) → ``(None, [name, *args])``
            — a CLI invocation (``_is_cli_invocation`` is then true).
          * unknown token → ``(None, [token, *args])`` so the CLI path emits a
            usage error.
          * no token (bare launch) → ``(None, [])`` — bring the Host forward.

        ``--help`` / ``-h`` is handled in ``__init__`` before this is consulted.
        """
        token, args, _help = self._cli_tokens()
        kind, name = self._resolve_token(token)
        if kind == "screen":
            return name, args
        if kind == "command":
            return None, [name, *args]
        if token is not None:
            return None, [token, *args]
        return None, []

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
        """Stable port from project title + OS user + run mode.

        Same inputs → same port, so the primary and a later forwarder
        independently agree where to talk without a shared file.  Keyed by
        user so two accounts on one machine each run their own Host, and by
        run mode (dev source vs compiled app) so a ``python .VIS/Host.py``
        dev Host and a compiled ``<title>.exe`` are separate single-instance
        domains.  Conceptually they are different apps that merely share
        data: launching one is not "a second instance" of the other (#151).

        Mode is read from the executable's basename: a dev run is launched
        by a Python interpreter (``python``/``pythonw``/``python3``), a
        compiled run by the app's own binary.  This survives editable
        installs (the dev exe is still ``python``) and onefile builds
        (``sys.executable`` is the app binary in both standalone and onefile).
        """
        try:
            user = getpass.getuser()
        except Exception:
            user = ""
        mode = "compiled" if is_compiled() else "dev"
        key = f"{self.Project.title}\x00{user}\x00{mode}".encode("utf-8")
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

    # ── CLI client (secondary instance: T side of the exchange) ──────────────

    def _is_cli_invocation(self) -> bool:
        """True when this launch is a Host-level CLI command, not a GUI launch.

        CLI = no recognized screen name but command-line args present.  A
        recognized screen (with or without ``--flags``) and a bare launch
        (no args = bring-to-front) are GUI.
        """
        return self._startup_screen is None and bool(self._startup_args)

    def _run_cli_client(self) -> None:
        """Resolve the CLI subcommand and run the exchange with the Host.

        The first positional arg is the command name (``<project> ping`` ->
        ``commands/c_ping.py``).  The command's ``_c_<name>(args)`` entry is
        the initial continuation: it runs on the Host and returns a
        terminal-side continuation (or None).  Unknown command -> usage error.
        """
        cmd = self._startup_args[0].lower()
        entry = self._resolve_command(cmd)
        if entry is None:
            self._cli_usage_error(cmd)
            return
        # Continuation is (callable, args) called as callable(*args); the
        # command entry takes the remaining args as a single list parameter
        # (`_c_<name>(args)`), so wrap that list in a 1-tuple.
        self._cli_exchange((entry, (self._startup_args[1:],)))

    @staticmethod
    def _run_screen_intercept(screen: str, args: list):
        """Host-side screen intercept: run ``commands.c_<screen>._c_<screen>``
        and act on its return (Option 2).

        Runs on the Host via the CLI exchange (``run_call`` on the Tk main
        loop), so it can open the screen.  ``_c_<screen>(args)`` returns:

          * ``None``  → open the screen with the original args.
          * ``list``  → open the screen with the (transformed) args.
          * ``(callable, args)`` → returned to the terminal, which runs it as a
            CLI response; the screen is NOT opened (e.g. arg validation failed).
        """
        host = _HOST_INSTANCE
        entry = Host._resolve_command(screen)
        try:
            result = entry(list(args)) if entry else None
        except Exception:
            import traceback
            traceback.print_exc()
            result = None
        if isinstance(result, tuple):
            return result  # terminal-side CLI response; no screen launch
        launch_args = result if isinstance(result, list) else list(args)
        if host is not None:
            host.open(screen, launch_args)
            host._raise_a_window()
        return None  # DONE — screen opened (or no Host to open it)

    @staticmethod
    def _resolve_command(cmd: str):
        """Import ``commands.c_<cmd>`` and return its ``_c_<cmd>`` entry, or
        None.  Lazy -- only the invoked command module is imported."""
        import importlib
        try:
            mod = importlib.import_module(f"commands.c_{cmd}")
        except Exception:
            return None
        entry = getattr(mod, f"_c_{cmd}", None)
        return entry if callable(entry) else None

    @staticmethod
    def _command_names() -> list:
        """Available command names from ``commands.__all__`` -- the manifest,
        built dynamically in dev and baked static into ``commands.pyd`` by the
        release build."""
        import importlib
        try:
            pkg = importlib.import_module("commands")
        except Exception:
            return []
        return sorted(
            m[2:] for m in (getattr(pkg, "__all__", []) or [])
            if isinstance(m, str) and m.startswith("c_")
        )

    # ── CLI registry: screens + commands, aliases, help ──────────────────────
    #
    # A CLI token can name a project SCREEN (``wom WorderEditor``) or a
    # standalone COMMAND (``wom ping``).  Either may carry ``__help__`` and
    # ``__alias__`` (and, for a screen, an ``_c_<Screen>`` intercept) via a
    # ``commands/c_<name>.py`` file.  ``__help__`` is a list of strings,
    # ``[0]`` short / ``[-1]`` long; ``__alias__`` is a str or list.

    @staticmethod
    def _as_list(val) -> list:
        """Normalize a str | list | None attribute to a list."""
        if val is None:
            return []
        return [val] if isinstance(val, str) else list(val)

    def _screen_names(self) -> list:
        """Every screen name the project knows."""
        try:
            from VIStk.Structures._Group import Group
            return [s.name for s in self.Project.Groups[Group.ALL].screenlist]
        except Exception:
            return []

    @staticmethod
    def _command_module(name: str):
        """Import ``commands.c_<name>`` and return the module, or None."""
        import importlib
        try:
            return importlib.import_module(f"commands.c_{name}")
        except Exception:
            return None

    @staticmethod
    def _iter_command_modules():
        """Yield ``(name, module)`` for each ``commands/c_<name>.py``."""
        import importlib
        try:
            pkg = importlib.import_module("commands")
        except Exception:
            return
        for m in (getattr(pkg, "__all__", []) or []):
            if not (isinstance(m, str) and m.startswith("c_")):
                continue
            try:
                mod = importlib.import_module(f"commands.{m}")
            except Exception:
                continue
            yield m[2:], mod

    def _cli_registry(self) -> tuple:
        """Build the unified CLI registry.

        Returns ``(entries, alias_map)``:
          * ``entries[name] = {"kind": "screen"|"command", "aliases": [...],
            "help": [short, ..., long]}``
          * ``alias_map[lower(name_or_alias)] = canonical_name`` (real names
            win; first alias wins on collision).

        Screens come from the project; a ``commands/c_<Screen>.py`` augments
        one with custom ``__help__`` / ``__alias__`` (+ optional intercept).
        A ``commands/c_<name>.py`` whose name is not a screen is a standalone
        command.  Screens with no augmenting file get auto help.
        """
        entries: dict = {}
        screen_set = set(self._screen_names())
        for sname in self._screen_names():
            mod = self._command_module(sname)
            aliases = self._as_list(getattr(mod, "__alias__", None)) if mod else []
            help_ = self._as_list(getattr(mod, "__help__", None)) if mod else []
            if not help_:
                help_ = [f"Launches the {sname} screen."]
            entries[sname] = {"kind": "screen", "aliases": aliases, "help": help_}
        for cname, mod in self._iter_command_modules():
            if cname in screen_set:
                continue  # screen augmentation, already folded in above
            aliases = self._as_list(getattr(mod, "__alias__", None))
            help_ = self._as_list(getattr(mod, "__help__", None)) or ["(no description)"]
            entries[cname] = {"kind": "command", "aliases": aliases, "help": help_}
        alias_map: dict = {}
        for name in entries:
            alias_map.setdefault(name.lower(), name)
        for name, info in entries.items():
            for a in info["aliases"]:
                alias_map.setdefault(a.lower(), name)  # real names already set
        return entries, alias_map

    def _resolve_token(self, token: str) -> tuple:
        """Resolve a CLI token to ``(kind, name)`` or ``(None, None)``.

        Exact name (screen or command) first, then alias; case-insensitive
        fallback.  Real names always beat aliases."""
        if not token:
            return None, None
        entries, alias_map = self._cli_registry()
        if token in entries:
            return entries[token]["kind"], token
        name = alias_map.get(token.lower())
        if name:
            return entries[name]["kind"], name
        return None, None

    def _cli_help_text(self, token) -> str:
        """Help output: the full listing (``token`` falsy) or one command's
        long help (``__help__[-1]``)."""
        entries, alias_map = self._cli_registry()
        if not token:
            lines = []
            for name in sorted(entries, key=str.lower):
                info = entries[name]
                head = " | ".join([name] + info["aliases"])
                lines.append(f"{head}\n\t{info['help'][0]}")
            return "\n".join(lines)
        name = token if token in entries else alias_map.get(token.lower())
        if not name or name not in entries:
            known = ", ".join(sorted(entries, key=str.lower))
            return (f"{self.Project.title}: unrecognized command: {token}\n"
                    f"known: {known}")
        return entries[name]["help"][-1]

    def _cli_tokens(self) -> tuple:
        """Parse ``sys.argv`` into ``(token, args, help_flag)``.

        ``token`` = first non-flag word (the command/screen name); ``args`` =
        the rest (screen ``--Flag value`` pairs preserved); ``help_flag`` =
        ``--help`` / ``-h`` present anywhere."""
        token = None
        args: list = []
        help_flag = False
        for arg in sys.argv[1:]:
            if arg.endswith(".py") and Path(arg).name.lower() == "host.py":
                continue
            if arg in ("--help", "-h"):
                help_flag = True
                continue
            if token is None and not arg.startswith("-"):
                token = arg
            else:
                args.append(arg)
        return token, args, help_flag

    def _cli_exchange(self, initial) -> None:
        """T side of the continuation-passing exchange.

        Opens one duplex connection to the running Host, sends the initial
        ``(callable, args)`` continuation, then pumps replies: each reply is
        either a ``call`` to run locally (its return value, if any, is a new
        continuation sent back to the Host) or ``done``.  Exits when no
        request is outstanding -- the running call produced no further
        continuation.
        """
        from VIStk.Objects import _cli
        try:
            conn = socket.create_connection(
                ("127.0.0.1", self._lock_port),
                timeout=self._LOCK_CONNECT_TIMEOUT,
            )
        except OSError:
            sys.stderr.write(
                f"{self.Project.title}: could not reach the running instance\n")
            return
        conn.settimeout(None)  # connect timeout only; the exchange blocks

        replies: queue.SimpleQueue = queue.SimpleQueue()

        def _reader():
            while True:
                m = _cli.recv_msg(conn)
                replies.put(m)
                if m is None:
                    break

        threading.Thread(
            target=_reader, daemon=True,
            name=f"VIStk-CLI-reader-{self.Project.title}",
        ).start()

        outstanding = 0
        try:
            _cli.send_msg(conn, _cli.serialize_call(initial))
            outstanding += 1
            while outstanding > 0:
                try:
                    m = replies.get(timeout=30)
                except queue.Empty:
                    sys.stderr.write(
                        f"{self.Project.title}: timed out waiting for the "
                        "running instance\n")
                    break
                if m is None:
                    break  # Host closed the connection
                outstanding -= 1
                if m.get("kind") != "call":
                    continue  # "done" (or unknown) -- request satisfied
                try:
                    out = _cli.run_call(m)
                except Exception:
                    import traceback
                    traceback.print_exc()
                    out = None
                if out is not None:
                    _cli.send_msg(conn, _cli.serialize_call(out))
                    outstanding += 1
        finally:
            try:
                conn.close()
            except Exception:
                pass

    def _cli_usage_error(self, cmd: str = "") -> None:
        """Print an unrecognized-command message listing known commands."""
        if not cmd:
            cmd = " ".join(sys.argv[1:]).strip()
        known = ", ".join(self._command_names())
        sys.stderr.write(
            f"{self.Project.title}: unrecognized command: {cmd}\n")
        if known:
            sys.stderr.write(f"known commands: {known}\n")

    def _cli_run_local(self, initial) -> None:
        """Run a CLI command's continuation chain in THIS process.

        Used when no Host is running: the command still executes, just with
        no GUI and no socket.  Both ends of the cross-process exchange
        collapse into one process, so the chain runs sequentially — call
        each ``(fn, args)`` continuation and follow its return value (a new
        continuation, or None to stop).  The in-process mirror of
        :meth:`_cli_exchange`, minus the serialization (the callables are
        already real objects here, not ``module:qualname`` references).

        Commands run with ``_HOST_INSTANCE`` still None, so any that read
        live Host state see "no Host" and degrade gracefully (e.g. ping
        reports ``open_windows=0``) rather than touching this half-built
        instance.
        """
        cont = initial
        while cont is not None:
            try:
                fn, fn_args = cont
            except (TypeError, ValueError):
                break  # malformed continuation — end the chain
            try:
                cont = fn(*fn_args)
            except Exception:
                import traceback
                traceback.print_exc()
                break

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
        """Accept connections; hand each to a per-connection handler thread.

        Runs on a background thread.  A GUI forward is one-shot, but a CLI
        exchange keeps its connection open as the reply channel, so each
        connection gets its own thread rather than being read inline here.
        """
        while self._lock_sock is not None:
            try:
                conn, _addr = self._lock_sock.accept()
            except OSError:
                break  # socket closed during shutdown
            threading.Thread(
                target=self._handle_conn, args=(conn,), daemon=True,
                name=f"VIStk-Host-conn-{self.Project.title}",
            ).start()

    def _handle_conn(self, conn: socket.socket) -> None:
        """Read framed requests off *conn* and queue them for the main loop.

        A GUI forward (``{"screen","args"}``) is a single message: queue it
        and close.  A CLI ``call`` keeps the connection open as the reply
        channel -- queue the call, then loop reading the continuations T
        sends back, until T disconnects.  Never touches Tk; the main-thread
        :meth:`_drain_ipc_queue` runs the calls and writes replies on *conn*.
        """
        from VIStk.Objects import _cli
        try:
            msg = _cli.recv_msg(conn)
            if msg is None:
                return
            if msg.get("kind") == "call":
                self._ipc_queue.put(("cli", msg, conn))
                while True:
                    m = _cli.recv_msg(conn)
                    if m is None:
                        break
                    self._ipc_queue.put(("cli", m, conn))
            else:
                self._ipc_queue.put(
                    ("open", msg.get("screen"), msg.get("args") or []))
        except Exception:
            pass
        finally:
            try:
                conn.close()
            except Exception:
                pass

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
        """Process queued requests on the Tk main loop.

        Called from :meth:`update`.  Opening a screen, touching windows, and
        running CLI calls all happen here on the main thread, hence the queue
        handoff from the connection handler threads.

        Items are tagged: ``("open", screen, args)`` for a GUI forward, and
        ``("cli", call_msg, conn)`` for a CLI call (whose result is written
        back to *conn* as the reply, or ``done`` when there is no
        continuation).
        """
        from VIStk.Objects import _cli
        try:
            while True:
                item = self._ipc_queue.get_nowait()
                tag = item[0]
                if tag == "open":
                    _, screen_name, args = item
                    if screen_name:
                        self.open(screen_name, args)
                    # Surface the running app: a relaunch should bring a
                    # window forward, not silently no-op.
                    self._raise_a_window()
                elif tag == "cli":
                    _, msg, conn = item
                    try:
                        out = _cli.run_call(msg)
                    except Exception:
                        import traceback
                        traceback.print_exc()
                        out = None
                    reply = (_cli.serialize_call(out)
                             if out is not None else _cli.DONE)
                    try:
                        _cli.send_msg(conn, reply)
                    except Exception:
                        pass
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

    def _daemonize(self) -> None:
        """Detach the primary GUI Host from the launching terminal (POSIX).

        Single ``fork`` + ``setsid``: the parent exits so the shell prompt
        returns immediately, and the child starts a new session with no
        controlling terminal and keeps running as the Host.  stdout/stderr
        are redirected to a log so GUI startup errors aren't lost; stdin to
        /dev/null.  Runs before the lock socket, Tk root, and listener
        thread exist, so the fork is single-threaded and pre-Tk.

        Mirrors the Windows GUI subsystem (the shell doesn't wait for a GUI
        launch); CLI commands skip this and stay foreground (#152).
        """
        try:
            if os.fork() > 0:
                os._exit(0)          # parent: release the terminal
        except OSError:
            return                   # fork unavailable — stay foreground
        os.setsid()                  # new session, drop controlling tty
        import tempfile
        log_path = os.path.join(tempfile.gettempdir(),
                                f"{self.Project.title}_host.log")
        try:
            devnull = os.open(os.devnull, os.O_RDONLY)
            os.dup2(devnull, 0)
            os.close(devnull)
            logfd = os.open(log_path,
                            os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
            os.dup2(logfd, 1)
            os.dup2(logfd, 2)
            os.close(logfd)
        except OSError:
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
            if is_compiled():
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
