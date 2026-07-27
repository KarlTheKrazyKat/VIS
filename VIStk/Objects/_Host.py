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

    The Host lives exactly as long as its windows: it starts with the first
    window, and once the last ``DetachedWindow`` closes it tears down the
    root, releases the single-instance lock, and the driver loop exits (see
    :meth:`_quit_if_no_windows`).  It is not a persistent background service
    -- closing every window ends the process.

    Navigation routes through ``_HOST_INSTANCE`` in-process.  There is no
    system tray; a localhost socket provides single-instance forwarding while
    a Host is alive.

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

        # Registered settings panels (name -> setup_fn), surfaced as extra
        # tabs in the Settings surface.  Set up-front — before any of the
        # single-instance / CLI early-returns below — so an app's Host.py
        # ``register_settings_panel`` call is safe even on a stub Host that
        # only forwards a launch to the already-running primary and exits.
        self._settings_panels: dict = {}
        # Registered menubar accessories (builder(parent) -> widget), mounted
        # right-aligned in each window's top tab-bar strip.  Same up-front
        # reasoning as ``_settings_panels``.
        self._menubar_accessories: list = []

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

        # Free the terminal for GUI launches before any threads / Tk exist.
        # The console twin (POSIX entry / Windows .com) is terminal-attached
        # so its CLI stdio flows to the shell; a GUI launch should release
        # the shell immediately.  POSIX: fork + setsid (#152).  Windows:
        # re-exec the sibling .exe (subsystem 2 = no console attachment,
        # the GUI mirror of the console .com).  CLI invocations stay
        # foreground on both platforms so their stdio works and the shell
        # waits.
        if not self._is_cli_invocation():
            if sys.platform == "win32":
                if self._reexec_as_gui_exe():
                    os._exit(0)
            else:
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

        # Materialise the default settings file on first run so every
        # available setting is visible/editable (idempotent; never clobbers
        # an existing file or user edits).
        self.Project.Settings.ensure_file()

        # Apply saved appearance (default font) to Tk's named fonts so all
        # default + ttk widgets inherit it.  Applied once at launch; live
        # restyling of open windows is deferred (see 0.6.1 changelog).
        self._apply_appearance()

        self.registered_tab_managers: list = []
        self.active_tab_manager = None
        self.detached_windows: list = []
        self.default_menu_setup = None

        # (``_settings_panels`` is initialised at the top of ``__init__`` so it
        # exists on every early-return path — see there.)

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

        # Self-terminate once every window is gone.  Set true the first time
        # a DetachedWindow exists, so the Host quits when the list empties
        # again -- but is NOT killed during startup before its first window
        # has been created.
        self._ever_had_window = False

        # 0.6.0 application-settings shutdown bookkeeping.
        self._shutting_down: bool = False
        """True while ``quit_host`` tears windows down.  The all-windows
        session snapshot is taken up-front there, so per-window
        ``DetachedWindow._on_close`` must not re-capture a single-window
        subset over it."""
        self._primary_window = None
        """The session's first ``DetachedWindow`` — source for the remembered
        ``window.last_geometry``."""
        self._restoring: bool = False
        """True while ``_open_startup`` reopens a remembered session, so the
        ``max_tabs`` limit doesn't truncate a session the user already had
        open (the limit is re-enforced on the next user-initiated open)."""

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
                    err_text: str | None = None
                    try:
                        out = _cli.run_call(msg)
                    except Exception as exc:
                        import traceback
                        traceback.print_exc()
                        out = None
                        # Send the error back so the terminal sees something
                        # instead of a silent DONE.  AttributeError on a Host
                        # method usually means a stale Host (this Host's code
                        # predates the function the new client just referenced).
                        hint = ""
                        if isinstance(exc, AttributeError) and "Host" in str(exc):
                            hint = ("\n  (this Host is running stale VIStk; "
                                    "restart it to pick up the new code.)")
                        err_text = (f"{self.Project.title}: Host call failed: "
                                    f"{type(exc).__name__}: {exc}{hint}")
                    if err_text is not None:
                        reply = _cli.serialize_call((print, (err_text,)))
                    elif out is not None:
                        reply = _cli.serialize_call(out)
                    else:
                        reply = _cli.DONE
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

    def _reexec_as_gui_exe(self) -> bool:
        """Detach the primary GUI Host from the terminal (Windows).

        The console twin (``<title>.com``, PE subsystem 3) is attached to
        the launching terminal — a GUI launch should free the shell.
        Re-launch the GUI ``<title>.exe`` (PE subsystem 2 = no console
        attachment) with the same argv and exit, mirroring the POSIX
        ``fork`` + ``setsid`` of :meth:`_daemonize`.  ``DETACHED_PROCESS``
        means the new process has no parent console; ``CREATE_NEW_PROCESS_GROUP``
        isolates it from Ctrl-C in the terminal.  stdout/stderr go to a
        log in tempdir so startup errors aren't dropped (a subsystem-2
        process has no console to print to).

        Returns ``True`` if the .exe was spawned (caller must exit
        immediately so the shell prompt returns).  Returns ``False`` when
        no re-exec is possible / wanted — already running as a .exe, dev
        mode under python.exe, .exe sibling missing — and the caller
        falls through to running in place (worse experience, but better
        than failing the launch).
        """
        if sys.platform != "win32":
            return False
        base, ext = os.path.splitext(sys.executable)
        if ext.lower() != ".com":
            return False
        exe_path = base + ".exe"
        if not os.path.exists(exe_path):
            return False
        import tempfile, subprocess
        log_path = os.path.join(tempfile.gettempdir(),
                                f"{self.Project.title}_host.log")
        try:
            log_fd = open(log_path, "ab")
            try:
                subprocess.Popen(
                    [exe_path, *sys.argv[1:]],
                    creationflags=(subprocess.DETACHED_PROCESS
                                   | subprocess.CREATE_NEW_PROCESS_GROUP),
                    stdin=subprocess.DEVNULL,
                    stdout=log_fd,
                    stderr=log_fd,
                    close_fds=True,
                )
            finally:
                log_fd.close()  # the .exe has its own duplicated handle
        except OSError:
            return False
        return True

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
        owner = self._window_for_tab_manager(self.active_tab_manager)
        if owner is not None:
            return owner
        return self.detached_windows[0] if self.detached_windows else None

    def _window_for_tab_manager(self, tm):
        """Return the DetachedWindow that owns *tm*, or ``None``.

        Walks each window's live SplitView tree rather than the seeded
        ``dw.tab_managers`` list (which isn't maintained across splits),
        so a pane created by ``SplitView.split`` still resolves to its
        window.
        """
        if tm is None:
            return None
        for dw in self.detached_windows:
            if tm in dw._split_view.all_tab_managers():
                return dw
        return None

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
                dw = self._window_for_tab_manager(tm)
                if dw is not None:
                    try:
                        dw.win.deiconify()
                        dw.win.lift()
                        dw.win.focus_force()
                    except Exception:
                        pass
                return

        # Enforce max_tabs limit — but not while restoring a remembered
        # session (the user already had these tabs open; don't truncate them
        # with mid-restore dialogs).  The limit applies to user-opened tabs.
        max_t = getattr(self.Project, "max_tabs", None)
        if max_t is not None and not self._restoring:
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

        # Pick a chromed window to host the tab.  A tabbed screen must never
        # land in a chromeless standalone window (its tab bar is hidden and
        # its SplitView is locked) — that's how navigating out of a
        # standalone screen, e.g. FloorView -> WorderEditor, used to leave
        # the new screen tab-less and headerless.
        target = self._tab_target()
        if target is None:
            # No chromed window exists yet — create one; it opens the tab.
            from VIStk.Objects._DetachedWindow import DetachedWindow
            dw = DetachedWindow(self, scr, args=args)
            return

        target.open_screen(scr, display, icon=icon, args=args)

    def _tab_target(self):
        """Return a TabManager in a chromed window to open a new tab into.

        Prefers the active pane when its owning window has chrome; otherwise
        the first non-chromeless window's focused pane.  Returns ``None``
        when every open window is chromeless (or none exist), so the caller
        spins up a fresh chromed DetachedWindow instead of stuffing a tabbed
        screen into a standalone window.
        """
        active = self.active_tab_manager
        owner = self._window_for_tab_manager(active)
        if active is not None and owner is not None and not owner.chromeless:
            return active
        for dw in self.detached_windows:
            if not dw.chromeless:
                return dw.tab_manager
        return None

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
            self._apply_tab_style()
            self._open_startup()
        self._drain_ipc_queue()
        self._tick_screens()
        self.root.update()
        self._quit_if_no_windows()

    def _open_startup(self) -> None:
        """Open the initial screen(s) on the Host's first update tick.

        Priority:

          1. An explicit ``<Project> <Screen>`` named on the command line —
             opened with its forwarded args.  A deliberate launch target wins,
             so session restore is skipped.
          2. ``host.remember_tabs`` + a saved ``host.last_tabs`` from the
             previous session — each still-installed screen reopened as a tab
             in launch order.  Screens no longer in the project are dropped
             silently (no missing-screen banner on restore).
          3. ``Project.default_screen``.
        """
        if self._startup_screen:
            self.open(self._startup_screen, self._startup_args)
            return

        if self.Project.Settings.get("host.remember_tabs"):
            last = self.Project.Settings.get("host.last_tabs") or []
            restorable = [b for b in last if self.Project.getScreen(b) is not None]
            if restorable:
                self._restoring = True
                try:
                    for base in restorable:
                        self.open(base)
                finally:
                    self._restoring = False
                return

        if self.Project.default_screen:
            self.open(self.Project.default_screen)

    def _quit_if_no_windows(self):
        """Shut the Host down once the last window has closed.

        The Host owns no visible window of its own, so an empty
        ``detached_windows`` list means nothing is on screen and there is no
        reason to keep the hidden root (and the single-instance lock) alive.

        ``_ever_had_window`` guards against quitting during startup, before
        the first window has been created, and against quitting an idle Host
        whose startup screen failed to open -- in both cases no window has
        ever existed, so the list being empty is not "all windows closed".
        """
        if self.detached_windows:
            self._ever_had_window = True
            return
        if not self._ever_had_window:
            return
        # Last window closed by the user: flush settings (the session was
        # persisted in that window's _on_close) before the root is gone.
        self._save_settings()
        self.Active = False
        self._close_lock()
        try:
            self.root.destroy()
        except Exception:
            pass

    def quit_host(self):
        """Close all DetachedWindows one by one, then shut down.

        Each window's ``_on_close()`` runs the two-pass veto check.  If any
        window vetoes (e.g. unsaved changes), the shutdown stops and the
        Host stays alive.
        """
        # Capture the session across ALL windows while they're still open,
        # but DON'T write it into settings yet — a vetoed close must leave
        # settings untouched.  _shutting_down suppresses the per-window
        # capture in _on_close so it can't double-write a single-window
        # subset over this full snapshot.
        self._shutting_down = True
        captured = self._capture_session()

        for dw in list(self.detached_windows):
            dw._on_close()
            if dw in self.detached_windows:
                # Window vetoed — abort shutdown; nothing was committed.
                self._shutting_down = False
                return

        self._commit_session(captured)
        self._save_settings()
        self.Active = False
        self._close_lock()
        try:
            self.root.destroy()
        except Exception:
            pass

    # ── Application settings: session persistence (0.6.0) ──────────────────────

    def _snapshot_open_tabs(self) -> list[str]:
        """Ordered ``base_name`` of every open tab across all windows/panes."""
        out: list[str] = []
        for dw in self.detached_windows:
            for tm in dw._split_view.all_tab_managers():
                for tab in tm._tabs.values():
                    b = tab.get("base_name")
                    if b:
                        out.append(b)
        return out

    def _capture_session(self, open_tabs: list | None = None, geo_window=None) -> dict:
        """Read session state into a plain dict WITHOUT touching settings.

        Honours the ``host.remember_tabs`` / ``window.remember_geometry``
        toggles (omits whatever is disabled).  Separating *capture* from
        *commit* matters for ``quit_host``: it must read tab/geometry state
        while the windows are still open, yet must NOT write anything into
        settings until the close has fully succeeded — a vetoed quit has to
        leave settings exactly as they were.  Never raises.

        Args:
            open_tabs:  Pre-captured base names (the per-window close path
                        passes these because its tabs are destroyed by the
                        time the close commits).  ``None`` snapshots all
                        currently-open windows live.
            geo_window: Window whose geometry to remember; ``None`` uses
                        :attr:`_primary_window`.
        """
        cap: dict = {}
        try:
            settings = self.Project.Settings
            if settings.get("host.remember_tabs"):
                cap["tabs"] = (open_tabs if open_tabs is not None
                               else self._snapshot_open_tabs())
            if settings.get("window.remember_geometry"):
                win = geo_window if geo_window is not None else self._primary_window
                if win is not None and win in self.detached_windows:
                    cap["geometry"] = win.win.geometry()
        except Exception:
            import traceback
            traceback.print_exc()
        return cap

    def _commit_session(self, cap: dict) -> None:
        """Write a captured session dict into settings (in memory).  Never raises."""
        try:
            settings = self.Project.Settings
            if "tabs" in cap:
                settings.set("host.last_tabs", cap["tabs"])
            if "geometry" in cap:
                settings.set("window.last_geometry", cap["geometry"])
        except Exception:
            import traceback
            traceback.print_exc()

    def _persist_session(self, open_tabs: list | None = None, geo_window=None) -> None:
        """Capture and immediately commit the session.

        For the *committed* single-window close path
        (``DetachedWindow._on_close``), where the window is already closing
        so there is no veto left to honour.
        """
        self._commit_session(self._capture_session(open_tabs, geo_window))

    def _save_settings(self) -> None:
        """Flush application settings to ``.VIS/settings.json`` when changed.

        Skips the write (and the mtime bump) when nothing was modified this
        session — the common case for an app that touched no settings.  Never
        raises (shutdown must not block).
        """
        try:
            if self.Project.Settings.dirty:
                self.Project.Settings.save()
        except Exception:
            import traceback
            traceback.print_exc()

    def _apply_appearance(self) -> None:
        """Apply the saved default font to Tk's named fonts at launch.

        Configures ``TkDefaultFont`` / ``TkTextFont`` / ``TkMenuFont`` /
        ``TkHeadingFont`` / ``TkFixedFont`` so default and ttk widgets inherit
        the project's ``appearance.font_family`` / ``appearance.font_size``.
        No-op when neither is set.  ``appearance.color_scheme`` is a stored
        placeholder with no effect yet (full theming: see 0.6.1).  Never
        raises — appearance must never block launch.
        """
        try:
            settings = self.Project.Settings
            family = settings.get("appearance.font_family")
            size = settings.get("appearance.font_size")
            if not family and not size:
                return
            import tkinter.font as tkfont
            for name in ("TkDefaultFont", "TkTextFont", "TkMenuFont",
                         "TkHeadingFont", "TkFixedFont"):
                try:
                    f = tkfont.nametofont(name)
                except Exception:
                    continue
                if family:
                    f.configure(family=family)
                if size:
                    try:
                        f.configure(size=int(size))
                    except (TypeError, ValueError):
                        pass
        except Exception:
            import traceback
            traceback.print_exc()

    def _apply_tab_style(self) -> None:
        """Resolve the saved tab style against the scheme and make it active.

        Runs on the Host's first update — after ``host.py`` has imported
        ``Screens/styles.py`` (which registers any custom looks and curates the
        offered list) and before the first window is built.  A saved
        ``appearance.tab_style`` that isn't in the app's offered list falls back
        to the app default.  Never raises — styling must not block launch.
        """
        try:
            from VIStk.Widgets import TabBar
            settings = self.Project.Settings
            scheme = settings.get("appearance.color_scheme") or "light"
            name = settings.get("appearance.tab_style")
            if name not in TabBar.offered_styles():
                name = TabBar.default_style()
            TabBar.set_tab_style(name, scheme=scheme)
        except Exception:
            import traceback
            traceback.print_exc()

    # ── Application settings: UI (0.6.0) ───────────────────────────────────────

    def register_settings_panel(self, name: str, setup_fn) -> None:
        """Register a custom panel for the built-in Settings window.

        The panel is called each time the Settings surface is built, with a
        ``ttk.Frame`` tab body to build into (mirrors a screen's
        ``setup(parent)``).  Two forms are supported:

        * ``setup_fn(frame)`` — self-managed: the panel builds its own widgets
          and reads/writes ``host.Project.Settings`` itself (call ``.save()``
          from within, or drive its own controls).
        * ``setup_fn(frame, ui)`` — integrated: *ui* is the settings
          controller; build fields with ``ui.add_check`` / ``ui.add_int`` /
          ``ui.add_combo`` and they ride the surface's own Save / Restore
          Defaults just like the General tab.

        ``name`` is the notebook tab label; registering the same name again
        replaces it.  Call before entering the update loop (typically in
        ``.VIS/Host.py``).
        """
        self._settings_panels[name] = setup_fn

    def register_menubar_accessory(self, builder) -> None:
        """Register a widget to sit at the top-right of the menubar strip.

        The native OS menubar can't host live widgets, so accessories live
        at the trailing (right) edge of each window's top tab-bar row — the
        first Tk-controlled strip, which reads as the menubar's right side.
        (Since 0.6.1 a *static* entry — text and/or a bitmap — CAN sit
        right-aligned on the real Windows menubar via
        ``HostMenu.add_project_command(..., image=<PIL image>,
        align="right")``; an accessory remains the path for anything that
        must stay a live widget — entries, comboboxes, animations.)

        ``builder(parent)`` is called once per window with the accessory
        container (a ``tk.Frame`` pinned to that corner); build a small widget
        into it (return value is ignored).  Typical use: a current-user badge,
        a status pill, a notifications bell.  The widget owns its own refresh
        (e.g. a ``widget.after`` tick) — the Host does not drive it.

        Call before entering the update loop (typically in ``.VIS/Host.py``).
        """
        self._menubar_accessories.append(builder)

    def _mount_menubar_accessories(self, tab_bar) -> None:
        """Build every registered accessory into *tab_bar*'s right-aligned slot.

        Called by :class:`DetachedWindow` for its primary pane's tab bar.  A
        vertical tab bar has no accessory slot (returns ``None``) and is
        skipped; a failing builder is isolated so it can't take down the
        window.
        """
        if not self._menubar_accessories:
            return
        slot = getattr(tab_bar, "get_accessory", lambda: None)()
        if slot is None:
            return
        for builder in self._menubar_accessories:
            try:
                builder(slot)
            except Exception:
                import traceback
                traceback.print_exc()

    def _open_settings(self) -> None:
        """Open the application Settings as a single-instance tab.

        Wired onto every window's HostMenu as the persistent **Settings**
        entry by :class:`DetachedWindow`.  Settings lives in the tab strip
        like a screen: an already-open Settings tab is focused rather than
        duplicated.  When there is no chromed window to host a tab (nothing
        but standalone windows, or none at all) it falls back to the legacy
        modal :class:`SettingsWindow`.
        """
        # Focus an existing Settings tab if one is open anywhere.
        tm, tab_id = self._find_tab_by_base("Settings")
        if tm is not None and tab_id is not None:
            tm.focus_tab(tab_id)
            dw = self._window_for_tab_manager(tm)
            if dw is not None:
                try:
                    dw.win.deiconify()
                    dw.win.lift()
                    dw.win.focus_force()
                except Exception:
                    pass
            return

        target = self._tab_target()
        if target is None:
            # No chromed window to host a tab — fall back to the modal window.
            from VIStk.Widgets._SettingsWindow import SettingsWindow
            parent = self.detached_windows[0].win if self.detached_windows else None
            SettingsWindow(self, parent).show()
            return

        from VIStk.Widgets._SettingsWindow import SettingsTab
        target.open_tab("Settings", SettingsTab(self), base_name="Settings")

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
