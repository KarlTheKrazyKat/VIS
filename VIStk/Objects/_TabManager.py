from __future__ import annotations

import builtins
import gc
import importlib
import importlib.util
import inspect
import marshal
import os
import queue
import sys
from tkinter import Frame
from types import ModuleType

from VIStk.Objects._Identity import new_id
from VIStk.Widgets._TabBar import TabBar, _BG_BAR


def set_tab_info(frame, info):
    """Set the characteristic info string for the tab that owns *frame*.

    Call this from within a screen's ``setup(parent)`` function.  ``info``
    may be a plain ``str`` (set once) or a ``tkinter.StringVar`` (traced; the
    tab label and window title update automatically whenever the variable
    changes).

    Example::

        def setup(parent):
            from VIStk.Objects import set_tab_info
            from tkinter import StringVar
            wo_var = StringVar(value="")
            set_tab_info(parent, wo_var)
            ...
    """
    mgr    = getattr(frame, "_vis_tab_manager", None)
    tab_id = getattr(frame, "_vis_tab_id",      None)
    if mgr is not None and tab_id is not None:
        mgr.set_tab_info(tab_id, info)


class _PerTabProxy:
    """Stand-in for ``Screens`` / ``modules`` inside a per-tab namespace.

    When the routing ``__import__`` rewrites ``import Screens.<X>.Y`` to
    ``import Screens.<X>__tab<id>.Y``, Python's ``IMPORT_NAME`` opcode
    binds the local name ``Screens`` to whatever the import returned.
    Subsequent attribute access (``Screens.<X>.Y.something``) walks
    attributes — never re-entering ``__import__`` — so the binding
    must answer for ``.<X>``.

    This proxy intercepts the screen-name attribute and returns the
    per-tab package; everything else (``Screens.defaults``,
    ``Screens.root``, ...) delegates to the real package.
    """
    __slots__ = ("_real", "_intercept_name", "_intercept_target")

    def __init__(self, real_pkg, intercept_name, intercept_target):
        object.__setattr__(self, "_real",             real_pkg)
        object.__setattr__(self, "_intercept_name",   intercept_name)
        object.__setattr__(self, "_intercept_target", intercept_target)

    def __getattr__(self, name):
        if name == self._intercept_name:
            return self._intercept_target
        return getattr(self._real, name)


class TabManager(Frame):
    """Manages the tabbed screen area of a DetachedWindow.

    ``TabManager`` is a ``Frame`` that fills its parent.  It owns two child
    frames:

    * ``tab_bar`` — a :class:`~VIStk.Widgets._TabBar.TabBar` packed along
      the top edge.
    * The *content frame* (internal) — fills the remaining space.

    Tab identity (0.4.7)
    --------------------
    Every opened tab is keyed by a stable integer ``tab_id`` allocated from
    :func:`VIStk.Objects._Identity.new_id`.  Display labels are mutable
    (see :meth:`set_tab_info`) and may collide; IDs disambiguate across
    panes and windows.

    Public methods accept either an ``int`` tab ID or a ``str`` display
    label.  When a label is passed, the first matching tab is used —
    lookup is non-deterministic in the presence of duplicate labels.
    Callers that hold a specific instance should pass the ID.

    Per-tab screen namespaces
    -------------------------
    :meth:`open_screen` builds an isolated Python namespace for each tab,
    registered in ``sys.modules`` under ``Screens.<name>__tab<id>`` and
    ``modules.<name>__tab<id>``.  The entry script and every ``f_*`` /
    ``m_*`` / ``j_*`` submodule are exec'd into per-tab module objects,
    so two tabs of the same screen do NOT share module-level state.
    See :meth:`_build_namespace`.

    Tab moves between panes (:meth:`move_tab`) destroy and rebuild the
    Tk frame (Tk can't reparent widgets) but preserve the per-tab
    namespace.  The screen's ``setup()`` runs again to bind widgets to
    the new frame; Python state (StringVar values, loaded data,
    closures) survives.

    Callbacks (receive ``tab_id: int`` as the first argument)::

        manager.on_tab_activate    = lambda tab_id, mod: ...
        manager.on_tab_deactivate  = lambda tab_id | None: ...
        manager.on_tab_popout      = lambda tab_id: ...
        manager.on_tab_detach      = lambda tab_id: ...
        manager.on_tab_refresh     = lambda tab_id: ...
        manager.on_tab_info_change = lambda tab_id, info: ...
        manager.on_tab_split       = lambda tab_id, direction, target_pane: ...

    Use :meth:`display_name` to resolve a ``tab_id`` back to its label.
    """

    def __init__(self, parent, position: str = "top", menubar=None, **kwargs):
        kwargs.setdefault("bg", _BG_BAR)
        super().__init__(parent, **kwargs)

        self.id: int = new_id()
        """Stable process-unique pane ID (0.4.7)."""

        self._tabs: dict[int, dict] = {}
        """tab_id -> {tab_id, display_name, frame, module, icon, base_name, info, _info_trace}

        ``module`` is the per-tab namespace built by :meth:`_build_namespace`.
        Hooks (``on_focused``, ``on_quit``, ``configure_menu``, ...) live
        inside that same namespace — no separate ``hooks`` key.
        """
        self._active: int | None = None
        self._position: str = position

        self._action_queue: queue.SimpleQueue = queue.SimpleQueue()
        self._action_pump_id: str | None = None
        self._menubar = menubar
        self._detached_window = None

        self.on_tab_activate   = None
        self.on_tab_deactivate = None
        self.on_tab_popout     = None
        self.on_tab_detach     = None
        self.on_tab_refresh    = None
        self.on_tab_info_change = None
        self.on_tab_split      = None

        self.tab_bar = TabBar(self, position=position)
        self.tab_bar.owner = self

        self._content = Frame(self)
        self._tab_bar_hidden: bool = False
        self._repack_layout()

        self.tab_bar.on_focus_change = self._on_focus_change
        self.tab_bar.on_tab_close    = self._on_close_request
        self.tab_bar.on_tab_popout   = self._on_popout_request
        self.tab_bar.on_tab_refresh  = self._on_refresh_request
        self.tab_bar.on_drag_detach  = self._on_detach_request
        self.tab_bar.on_drag_merge   = self._on_merge_request
        self.tab_bar.on_tab_split    = self._on_split_request

        # Start the action-queue pump. Project.open() enqueues navigation
        # lambdas here; without a consumer they'd sit forever.
        self._action_pump_id = self.after(16, self._pump_actions)
        self.bind("<Destroy>", self._stop_action_pump, add="+")

    # ── Action queue pump ─────────────────────────────────────────────────────

    def _pump_actions(self):
        """Drain queued navigation callables on the Tk main loop.

        Exceptions raised by queued callables are printed to stderr —
        previously swallowed silently, which made debugging "tab
        didn't open and there's no error" scenarios impossible.
        """
        try:
            while True:
                fn = self._action_queue.get_nowait()
                try:
                    fn()
                except Exception:
                    import traceback
                    traceback.print_exc()
        except queue.Empty:
            pass
        try:
            self._action_pump_id = self.after(16, self._pump_actions)
        except Exception:
            self._action_pump_id = None

    def _stop_action_pump(self, event=None):
        """Cancel the pending pump on widget destruction."""
        if event is not None and event.widget is not self:
            return
        if self._action_pump_id is not None:
            try:
                self.after_cancel(self._action_pump_id)
            except Exception:
                pass
            self._action_pump_id = None

    # ── Layout ─────────────────────────────────────────────────────────────────

    def _repack_layout(self):
        """Pack tab_bar and _content based on the current position setting.

        When ``_tab_bar_hidden`` is set the tab bar is omitted entirely and
        the content frame fills the pane — used by chromeless standalone
        DetachedWindows that host a single non-tabbed screen.
        """
        self.tab_bar.pack_forget()
        self._content.pack_forget()
        if not self._tab_bar_hidden:
            if self._position in ("top", "bottom"):
                self.tab_bar.pack(side=self._position, fill="x")
            else:
                self.tab_bar.pack(side=self._position, fill="y")
        if self._position in ("top", "bottom"):
            self._content.pack(side="top", fill="both", expand=True)
        else:
            self._content.pack(side="left", fill="both", expand=True)

    def set_position(self, position: str):
        """Change the tab bar position and update the layout."""
        self._position = position
        self.tab_bar.set_position(position)
        self._repack_layout()

    def hide_tab_bar(self):
        """Hide the tab bar — used for chromeless standalone windows."""
        if not self._tab_bar_hidden:
            self._tab_bar_hidden = True
            self._repack_layout()

    def show_tab_bar(self):
        """Restore the tab bar after :meth:`hide_tab_bar`."""
        if self._tab_bar_hidden:
            self._tab_bar_hidden = False
            self._repack_layout()

    # ── Identity helpers ───────────────────────────────────────────────────────

    def _resolve_id(self, key) -> int | None:
        """Resolve *key* (int tab_id or str display label) to a tab_id."""
        if isinstance(key, int) and not isinstance(key, bool):
            return key if key in self._tabs else None
        if isinstance(key, str):
            return self._id_for_display(key)
        return None

    def _id_for_display(self, label: str) -> int | None:
        """Return the first tab_id whose display_name equals *label*, else None.

        Non-deterministic when multiple tabs share *label*.  Prefer holding
        the tab_id returned by :meth:`open_tab`.
        """
        for tab_id, entry in self._tabs.items():
            if entry.get("display_name") == label:
                return tab_id
        return None

    def display_name(self, tab_id: int) -> str | None:
        """Return the current display name of *tab_id*, or None."""
        entry = self._tabs.get(tab_id)
        return entry.get("display_name") if entry else None

    # ── Public API ─────────────────────────────────────────────────────────────

    @property
    def active(self) -> int | None:
        """Tab ID of the currently active tab (0.4.7)."""
        return self._active

    @property
    def active_module(self):
        """Return the module of the currently active tab, or None."""
        if self._active is not None and self._active in self._tabs:
            return self._tabs[self._active].get("module")
        return None

    # ── Menu delegation ───────────────────────────────────────────────────────

    def register_menu_item(self, label: str, command):
        """Register a single menu item (delegates to the window's menubar)."""
        if self._menubar:
            self._menubar.set_screen_items([{"label": label, "command": command}])

    def add_cascade(self, label: str, items: list[dict]):
        """Add a cascade menu (delegates to the window's menubar)."""
        if self._menubar:
            self._menubar.set_screen_items(items, label=label)

    # ── Navigation ────────────────────────────────────────────────────────────

    def navigate(self, name: str, args=None):
        """Navigate this pane to a new screen.

        Tears down the current screen (calling on_quit), then opens a
        fresh tab for *name* via :meth:`open_screen`.
        """
        from VIStk.Objects._Host import _HOST_INSTANCE
        if _HOST_INSTANCE is None:
            return

        if self._active is not None and self._active in self._tabs:
            entry = self._tabs[self._active]
            module = entry.get("module")
            quit_fn = getattr(module, "on_quit", None)
            if quit_fn:
                try:
                    if quit_fn() is False:
                        return  # vetoed
                except Exception:
                    pass
            self.close_tab(self._active)

        scr = _HOST_INSTANCE.Project.getScreen(name)
        if scr is None:
            return
        icon    = _HOST_INSTANCE._load_tab_icon(scr)
        display = _HOST_INSTANCE._unique_display_name(name)
        tab_id  = self.open_screen(scr, display, icon=icon)

        if args is not None and tab_id is not None:
            module = self._tabs[tab_id].get("module")
            if module and hasattr(module, "ArgHandler"):
                try:
                    module.ArgHandler.handle(args)
                except Exception:
                    pass

    def _cleanup_screen_modules(self, screen_name: str):
        """Remove EVERY per-tab sys.modules entry for *screen_name*.

        Sweeps every ``Screens.<screen_name>__tab*`` and
        ``modules.<screen_name>__tab*`` registration.  Kept as a
        screen-wide purge for callers that don't have a specific tab_id;
        single-tab close uses :meth:`_destroy_namespace_entries` instead.
        """
        prefixes = (
            f"Screens.{screen_name}__tab",
            f"modules.{screen_name}__tab",
        )
        to_delete = [k for k in sys.modules if any(k.startswith(p) for p in prefixes)]
        for key in to_delete:
            del sys.modules[key]
        gc.collect()

    def _cleanup_all_modules(self):
        """Strip per-tab sys.modules entries for every tab in this manager.

        Called by ``DetachedWindow._destroy_pane`` when a pane is
        removed before its tabs went through ``close_tab``.  Defensive —
        tabs closed via ``close_tab`` clean up their own namespace.
        """
        for tab_id, entry in list(self._tabs.items()):
            base_name = entry.get("base_name") or entry.get("display_name")
            if base_name:
                self._destroy_namespace_entries(tab_id, base_name)

    # ── Per-tab namespace construction ────────────────────────────────────────

    def _build_namespace(self, tab_id: int, scr) -> ModuleType:
        """Build a fresh per-tab namespace for *scr* and exec its entry into it.

        Registers per-tab versions of the screen's UI subpackage at
        ``Screens.<name>__tab<id>`` (with each ``f_*`` / ``j_*`` as a
        submodule) and the logic subpackage at ``modules.<name>__tab<id>``
        (with each ``m_*`` as a submodule).  Every submodule shares a
        routing ``__builtins__`` whose ``__import__`` redirects absolute
        ``Screens.<name>.*`` / ``modules.<name>.*`` imports to the
        per-tab variants; everything else passes through unchanged.

        Pre-registers all submodules in ``sys.modules`` *before* exec'ing
        any of them so circular imports between them resolve.

        Returns the per-tab package.  Caller (:meth:`open_screen`) stores
        it as ``tab_entry["module"]`` and invokes
        ``module.setup(frame)`` / ``module.loop()`` / etc. on it.
        """
        pkg_name     = f"Screens.{scr.name}__tab{tab_id}"
        mod_pkg_name = f"modules.{scr.name}__tab{tab_id}"

        pkg = ModuleType(pkg_name)
        pkg.__path__ = [scr.path]
        sys.modules[pkg_name] = pkg

        mod_pkg = ModuleType(mod_pkg_name)
        mod_pkg.__path__ = [scr.m_path]
        sys.modules[mod_pkg_name] = mod_pkg

        # Routing builtins reference the per-tab packages, so they must
        # exist in sys.modules first (already done above).
        routing_builtins = self._make_routing_import(
            tab_id, scr.name, pkg, mod_pkg,
        )
        pkg.__builtins__     = routing_builtins
        mod_pkg.__builtins__ = routing_builtins

        # Load code objects — from source files in dev, from the wrapper
        # .pyd's ``_EMBEDDED`` dict in a compiled release build.
        entry_code, screens_codes, modules_codes = self._load_screen_codes(scr)

        # Pre-register every submodule under both per-tab packages with
        # its pending code object attached.  Exec is deferred: the
        # routing __import__ calls ``_ensure_executed`` to run any
        # pending code at first reference.  This handles import-order
        # surprises where module A (alphabetically earlier) does
        # ``from B import name`` before B has been exec'd — eager
        # exec in sorted order would return B's empty shell and
        # raise ImportError on the name lookup.
        for codes, parent_pkg, parent_name in (
            (screens_codes, pkg,     pkg_name),
            (modules_codes, mod_pkg, mod_pkg_name),
        ):
            for stem, code in codes.items():
                full_name = f"{parent_name}.{stem}"
                sub = ModuleType(full_name)
                sub.__builtins__ = routing_builtins
                sub.__vistk_pending_code__ = code   # exec-on-demand marker
                sys.modules[full_name] = sub
                setattr(parent_pkg, stem, sub)

        # Exec the entry script into the per-tab package itself.  Its
        # top-level imports cascade through the routing __import__,
        # which exec's each submodule on demand in the correct order.
        # After this returns, ``pkg.setup``, ``pkg.loop``, etc. are
        # populated in ``pkg.__dict__``.
        exec(entry_code, pkg.__dict__)
        return pkg

    @staticmethod
    def _ensure_executed(name: str):
        """Walk the dotted *name* and exec any per-tab submodule that
        still carries pending code.

        Called by the routing ``__import__`` before returning a
        rewritten target so callers always see a fully-populated
        module.  Safe to call repeatedly — pending-code attr is
        cleared atomically before exec runs (sentinel prevents
        recursive exec loops on circular imports).
        """
        parts = name.split(".")
        for i in range(1, len(parts) + 1):
            sub_name = ".".join(parts[:i])
            mod = sys.modules.get(sub_name)
            if mod is None:
                continue
            code = getattr(mod, "__vistk_pending_code__", None)
            if code is None:
                continue
            # Clear marker before exec to defeat recursion in
            # circular-import chains: if A.exec → triggers import
            # of B → triggers import of A again, the second pass
            # finds no pending code and returns A's current
            # (partial) state — same semantics as Python's normal
            # circular-import handling.
            del mod.__vistk_pending_code__
            exec(code, mod.__dict__)

    def _load_screen_codes(self, scr):
        """Return ``(entry_code, screens_codes, modules_codes)`` for *scr*.

        Each return value is either a single code object (entry) or a
        ``{stem: code_object}`` dict (screens/modules).

        Resolution: prefer the wrapper ``.pyd``'s ``_EMBEDDED`` dict if
        one is on the import path (compiled release), otherwise read
        source files from disk (dev).  We probe with
        :func:`importlib.util.find_spec` and only import when we know
        the spec points at a compiled extension — importing a source
        ``.py`` would execute its top-level code with normal builtins
        (no per-tab routing), polluting ``sys.modules`` and breaking
        the per-tab isolation invariant.

        Detection: does ``scr.script_path`` exist on disk?
        ``script_path`` resolves to ``p_project + "/" + scr.script``,
        which in dev points at the project's checkout (where the .py
        files live) and in a release install points at the runtime/
        root (where they don't — only wrapper .pyds ship there).
        The release pipeline wipes runtime/ at the start of every
        full build (see ``Release.release``), so stale .py leftovers
        from previous pipelines no longer mislead this check.

        We tried two other discriminators and they both failed:

        * ``importlib.util.find_spec(stem)`` — returns ``None`` inside
          Nuitka's frozen runtime for loose .pyd files at the install
          root, even when ``importlib.import_module`` of the same name
          succeeds.
        * ``sys.frozen`` — set by PyInstaller and Nuitka's onefile
          mode, but NOT by Nuitka's ``--standalone`` mode, which is
          what we ship.

        The presence-of-source check is the simplest signal that
        actually distinguishes the two cases without relying on
        per-tool conventions.
        """
        if os.path.exists(scr.script_path):
            return self._load_codes_from_source(scr)
        return self._load_codes_from_embedded(scr)

    def _load_codes_from_source(self, scr):
        """Read source .py files and return compiled code objects."""
        entry = self._compile_file(scr.script_path)
        screens = self._compile_dir(scr.path)   if os.path.isdir(scr.path)   else {}
        modules = self._compile_dir(scr.m_path) if os.path.isdir(scr.m_path) else {}
        return entry, screens, modules

    def _load_codes_from_embedded(self, scr):
        """Read marshalled bytecode from the compiled wrapper's ``_EMBEDDED``
        dict and unmarshal into code objects.

        The wrapper is the compiled .pyd produced by the release pipeline
        (see ``Release._build_screen_wrapper``).  It exposes a single
        attribute, ``_EMBEDDED``, with shape::

            {"entry":   <bytes>,
             "screens": {stem: <bytes>, ...},
             "modules": {stem: <bytes>, ...}}

        where each ``<bytes>`` value is the output of ``marshal.dumps``
        on the original source's compiled code object.
        """
        stem = os.path.splitext(scr.script)[0]
        mod = importlib.import_module(stem)
        e = mod._EMBEDDED
        return (
            marshal.loads(e["entry"]),
            {k: marshal.loads(v) for k, v in e.get("screens", {}).items()},
            {k: marshal.loads(v) for k, v in e.get("modules", {}).items()},
        )

    @staticmethod
    def _compile_file(path: str):
        """Read one source file and return its compiled code object."""
        with open(path, "rb") as f:
            return compile(f.read(), path, "exec")

    @classmethod
    def _compile_dir(cls, src_dir: str) -> dict:
        """Return ``{stem: code_object}`` for every ``*.py`` in *src_dir*
        except ``__init__.py``."""
        out: dict = {}
        for fname in sorted(os.listdir(src_dir)):
            if fname.endswith(".py") and fname != "__init__.py":
                stem = fname[:-3]
                out[stem] = cls._compile_file(f"{src_dir}/{fname}")
        return out

    def _make_routing_import(self, tab_id: int, screen_name: str,
                              per_tab_screens, per_tab_modules):
        """Return a ``__builtins__`` dict whose ``__import__`` reroutes
        ``Screens.<screen_name>.*`` and ``modules.<screen_name>.*`` to
        the per-tab versions, leaving everything else unchanged.

        For ``import X.Y.Z`` (empty fromlist) returns a
        :class:`_PerTabProxy` so subsequent attribute access on the
        local ``Screens`` / ``modules`` binding routes through the
        per-tab namespace.  For ``from X.Y import Z`` (non-empty
        fromlist) returns the rewritten leaf module directly — Python
        applies ``getattr(leaf, "Z")`` and the leaf IS the per-tab
        module, so the right thing happens.
        """
        real = builtins.__import__
        sp, ts = f"Screens.{screen_name}", f"Screens.{screen_name}__tab{tab_id}"
        mp, tm = f"modules.{screen_name}", f"modules.{screen_name}__tab{tab_id}"

        # Ensure the real top-level packages exist in sys.modules before
        # wrapping them — they hold shared modules like ``Screens.defaults``
        # and ``modules.menu`` that screen code passes through to.  First
        # screen open will be the import trigger; subsequent opens find
        # them already cached.
        real_screens = sys.modules.get("Screens") or importlib.import_module("Screens")
        real_modules = sys.modules.get("modules") or importlib.import_module("modules")

        screens_proxy = _PerTabProxy(real_screens, screen_name, per_tab_screens)
        modules_proxy = _PerTabProxy(real_modules, screen_name, per_tab_modules)

        ensure = self._ensure_executed

        def routing_import(name, glb=None, loc=None, fromlist=(), level=0):
            if level == 0:
                rewritten = None
                proxy = None
                if name == sp or name.startswith(sp + "."):
                    rewritten = ts + name[len(sp):]
                    proxy = screens_proxy
                elif name == mp or name.startswith(mp + "."):
                    rewritten = tm + name[len(mp):]
                    proxy = modules_proxy

                if rewritten is not None:
                    # Exec the target module's pending code (if any)
                    # before real __import__ uses it — otherwise the
                    # leaf comes back as an empty pre-registered shell.
                    ensure(rewritten)
                    result = real(rewritten, glb, loc, fromlist, 0)
                    # ``from <pkg> import <name>`` may name a submodule.
                    # Ensure those are exec'd too; real __import__ won't
                    # re-trigger load on pre-registered modules.
                    if fromlist:
                        for item in fromlist:
                            if item == "*":
                                continue
                            ensure(f"{rewritten}.{item}")
                    return result if fromlist else proxy

                # ``from modules import <screen_name>`` /
                # ``from Screens import <screen_name>`` — the new stitch
                # convention emits this pattern.  Real ``__import__``
                # would return the on-disk ``modules`` / ``Screens``
                # package and ``IMPORT_FROM`` would fail because the
                # package doesn't expose the per-tab module as an
                # attribute.  Return the proxy instead — its
                # ``__getattr__`` answers for ``screen_name`` with the
                # per-tab module.
                if fromlist and screen_name in fromlist:
                    if name == "modules":
                        ensure(tm)
                        return modules_proxy
                    if name == "Screens":
                        ensure(ts)
                        return screens_proxy
            return real(name, glb, loc, fromlist, level)

        nb = dict(builtins.__dict__)
        nb["__import__"] = routing_import
        return nb

    def _destroy_namespace_entries(self, tab_id: int, screen_name: str):
        """Drop this tab's per-tab sys.modules entries.

        Targeted counterpart to :meth:`_cleanup_screen_modules` —
        removes only ``Screens.<screen_name>__tab<tab_id>*`` and
        ``modules.<screen_name>__tab<tab_id>*``, leaving sibling tabs
        of the same screen intact.
        """
        prefixes = (
            f"Screens.{screen_name}__tab{tab_id}",
            f"modules.{screen_name}__tab{tab_id}",
        )
        to_del = [k for k in sys.modules
                  if any(k == p or k.startswith(p + ".") for p in prefixes)]
        for k in to_del:
            del sys.modules[k]

    # ── Tab opening ───────────────────────────────────────────────────────────

    def open_screen(self, scr, display: str, icon=None,
                    insert_idx: int = -1, tab_id: int | None = None) -> int | None:
        """Open *scr* as a new tab, building a fresh per-tab namespace.

        Allocates ``tab_id`` (or uses the supplied one — for
        force-refresh and split-rebuild scenarios that preserve
        identity), builds the per-tab namespace via
        :meth:`_build_namespace`, then registers the tab via
        :meth:`open_tab` with the freshly-built module.
        """
        if tab_id is None:
            existing = self._id_for_display(display)
            if existing is not None:
                self.tab_bar.focus_tab(existing)
                return None
            tab_id = new_id()
        elif tab_id in self._tabs:
            return None

        instance = self._build_namespace(tab_id, scr)
        return self.open_tab(display, instance, icon=icon,
                             insert_idx=insert_idx, base_name=scr.name,
                             tab_id=tab_id)

    def open_tab(self, name: str, module, hooks=None, icon=None,
                 insert_idx: int = -1, base_name: str = None,
                 tab_id: int | None = None) -> int | None:
        """Place an already-built *module* as a new tab.

        Low-level entry point used by:
          * :meth:`open_screen` after building a per-tab namespace
          * :meth:`move_tab` to place a moved tab's preserved namespace
          * ``SplitView`` snapshot/rebuild to restore tabs with their
            existing per-tab namespaces

        The legacy *hooks* argument is accepted for back-compat but
        ignored — under the per-tab namespace design hooks live inside
        ``module`` (the per-tab namespace).

        Returns the tab's ``tab_id`` on success, ``None`` if a tab with
        this exact display name already exists in *this* pane (callers
        with the same label across panes are fine).
        """
        # Reject only if the same ``tab_id`` is already registered —
        # SplitView rebuilds call with an explicit ``tab_id`` and require
        # the call to succeed even when a tab with a matching display
        # label is in the pane (it shouldn't be, because the pane is
        # fresh, but defensive ID-based gating is safer).
        if tab_id is not None and tab_id in self._tabs:
            return None

        # For fresh-ID callers: suppress duplicate labels in the same pane
        # by focusing the existing tab instead of creating a visual clone.
        if tab_id is None:
            existing = self._id_for_display(name)
            if existing is not None:
                self.tab_bar.focus_tab(existing)
                return None
            tab_id = new_id()

        frame = Frame(self._content)
        frame.place(relx=0, rely=0, relwidth=1, relheight=1)

        # Let screens call set_tab_info(parent, ...) from inside setup()
        frame._vis_tab_id      = tab_id
        frame._vis_tab_manager = self

        self._tabs[tab_id] = {
            "tab_id":        tab_id,
            "display_name":  name,
            "frame":         frame,
            "module":        module,
            "icon":          icon,
            "base_name":     base_name if base_name is not None else name,
            "info":          "",
            "_info_trace":   None,
        }

        if module and hasattr(module, "setup"):
            try:
                module.setup(frame)
            except Exception:
                # Surface the failure: print a traceback to stderr (visible
                # in dev runs and console-attached frozen builds) and
                # render an inline error panel inside the otherwise-blank
                # tab so windowed Windows installs (where stderr goes
                # nowhere) still tell the user what failed (#131).
                import traceback as _tb
                import sys as _sys
                err_text = _tb.format_exc()
                try:
                    _sys.stderr.write(
                        f"\n[VIStk] setup() failed for tab "
                        f"{name!r}:\n{err_text}\n"
                    )
                    _sys.stderr.flush()
                except Exception:
                    pass
                try:
                    from tkinter import Label
                    Label(
                        frame,
                        text=(
                            f"setup() raised an exception for "
                            f"{name}:\n\n{err_text}"
                        ),
                        bg="#ffe5e5", fg="#600",
                        justify="left", anchor="nw",
                        wraplength=1100,
                        font=("Consolas", 9),
                    ).pack(fill="both", expand=True, padx=12, pady=12)
                except Exception:
                    pass

        self.tab_bar.open_tab(tab_id, name, icon=icon, insert_idx=insert_idx)
        return tab_id

    def move_tab(self, source_mgr: "TabManager", tab_id: int,
                 insert_idx: int = -1) -> int | None:
        """Move *tab_id* from *source_mgr* to this manager.

        Tk widgets can't be reparented cleanly, so the source frame is
        destroyed and a fresh one built under this manager's content
        frame; ``setup(new_frame)`` runs again to bind widgets to it.
        The per-tab sys.modules entries (and the per-tab namespace they
        contain) are preserved — module-level state like ``StringVar``
        values, loaded LRF data, and callback closures survive the move.

        The ``tab_id`` is preserved across the move so external
        references (recorded focus IDs, pane-parent lookups) stay valid.

        Returns the preserved ``tab_id`` on success, ``None`` if the tab
        wasn't found in *source_mgr* or destination already holds the ID.
        """
        if tab_id not in source_mgr._tabs:
            return None
        if tab_id in self._tabs:
            return None

        entry     = source_mgr._tabs[tab_id]
        display   = entry["display_name"]
        icon      = entry.get("icon")
        base_name = entry.get("base_name", display)
        module    = entry.get("module")
        trace     = entry.get("_info_trace")
        info_str  = entry.get("info", "")

        # Tear down source pane's view of this tab without touching
        # sys.modules — the per-tab namespace lives on.
        if source_mgr._active == tab_id:
            source_mgr._deactivate(tab_id)
            source_mgr._active = None
        if trace is not None:
            var, tid = trace
            try:
                var.trace_remove("write", tid)
            except Exception:
                pass
        try:
            entry["frame"].destroy()
        except Exception:
            pass
        del source_mgr._tabs[tab_id]
        source_mgr.tab_bar.close_tab(tab_id)

        # Build the new frame and re-run setup with the preserved module
        new_id_returned = self.open_tab(display, module, icon=icon,
                                         insert_idx=insert_idx,
                                         base_name=base_name, tab_id=tab_id)
        if new_id_returned is None:
            return None

        # Restore the info trace on the new pane (prefer StringVar if
        # the caller wired one originally)
        if trace is not None:
            var, _ = trace
            self.set_tab_info(tab_id, var)
        elif info_str:
            self.set_tab_info(tab_id, info_str)

        return tab_id

    def close_tab(self, key, skip_on_quit: bool = False) -> bool:
        """Close the tab identified by *key* (tab_id or display label).

        Destroys the per-tab namespace as part of teardown.  Callers
        that want to move a tab between managers without losing its
        namespace should use :meth:`move_tab` instead.

        Args:
            key:          Tab ID (int) or display label (str).
            skip_on_quit: If True, skip the on_quit hook (used when
                DetachedWindow has already checked it).
        """
        tab_id = self._resolve_id(key)
        if tab_id is None:
            return False

        entry     = self._tabs[tab_id]
        base_name = entry.get("base_name") or entry.get("display_name", "")

        # Call on_quit unless skipped (e.g. window close already checked)
        if not skip_on_quit:
            module  = entry.get("module")
            quit_fn = getattr(module, "on_quit", None)
            if quit_fn:
                try:
                    if quit_fn() is False:
                        return False  # vetoed
                except Exception:
                    pass

        # Clean up StringVar trace if present
        trace_info = entry.get("_info_trace")
        if trace_info is not None:
            var, tid = trace_info
            try:
                var.trace_remove("write", tid)
            except Exception:
                pass

        if self._active == tab_id:
            self._deactivate(tab_id)
            self._active = None

        entry["frame"].destroy()

        # Drop per-tab sys.modules entries for this tab.  Sibling tabs
        # of the same screen are unaffected.
        if base_name:
            self._destroy_namespace_entries(tab_id, base_name)

        del self._tabs[tab_id]
        self.tab_bar.close_tab(tab_id)
        return True

    def focus_tab(self, key) -> bool:
        """Focus the tab identified by *key* (tab_id or display label)."""
        tab_id = self._resolve_id(key)
        if tab_id is None:
            return False
        return self.tab_bar.focus_tab(tab_id)

    def has_tab(self, key) -> bool:
        """Return whether *key* identifies an open tab."""
        return self._resolve_id(key) is not None

    def force_refresh_tab(self, key) -> bool:
        """Close and reopen the identified tab, re-running ``setup`` with
        a fresh per-tab namespace.

        Preserves the same ``tab_id`` across the refresh so external
        references survive.  In-tab state is intentionally lost — that's
        the point of "refresh."  For state-preserving moves between
        panes, use :meth:`move_tab`.
        """
        tab_id = self._resolve_id(key)
        if tab_id is None:
            return False
        idx       = self.tab_bar.get_tab_idx(tab_id)
        entry     = self._tabs[tab_id]
        display   = entry["display_name"]
        icon      = entry.get("icon")
        base_name = entry.get("base_name", display)

        from VIStk.Objects._Host import _HOST_INSTANCE
        if _HOST_INSTANCE is None:
            return False
        scr = _HOST_INSTANCE.Project.getScreen(base_name)
        if scr is None:
            return False

        if not self.close_tab(tab_id, skip_on_quit=True):
            return False

        new_tab_id = self.open_screen(scr, display, icon=icon,
                                       insert_idx=idx, tab_id=tab_id)
        return new_tab_id is not None

    def set_tab_info(self, key, info) -> None:
        """Set or trace the characteristic info for the identified tab.

        ``info`` may be a plain ``str`` or a ``tkinter.StringVar``.
        Replaces any previously registered trace.
        """
        tab_id = self._resolve_id(key)
        if tab_id is None:
            return
        # Remove existing trace if any
        old = self._tabs[tab_id].get("_info_trace")
        if old is not None:
            old_var, old_tid = old
            try:
                old_var.trace_remove("write", old_tid)
            except Exception:
                pass
            self._tabs[tab_id]["_info_trace"] = None

        # Detect StringVar by duck-typing
        if hasattr(info, "trace_add") and callable(info.trace_add):
            var = info
            tid = var.trace_add("write",
                                lambda *_: self._update_tab_info(tab_id, var.get()))
            self._tabs[tab_id]["_info_trace"] = (var, tid)
            self._update_tab_info(tab_id, var.get())
        else:
            self._update_tab_info(tab_id, str(info))

    # ── Hook lookup ────────────────────────────────────────────────────────────

    def _get_hook(self, tab_id: int, hook_name: str):
        """Look up *hook_name* on the tab's per-tab namespace.

        Under the per-tab namespace design hooks
        (``on_focused``, ``on_unfocused``, ``on_quit``,
        ``configure_menu``, ``has_unsaved``) and the rest of the
        screen's API both live in the same per-tab module — no separate
        hooks module to consult.
        """
        entry = self._tabs.get(tab_id, {})
        return getattr(entry.get("module"), hook_name, None)

    # ── Internal ───────────────────────────────────────────────────────────────

    def _update_tab_info(self, tab_id: int, info: str):
        """Update the stored info string and propagate to tab label + callback."""
        if tab_id not in self._tabs:
            return
        self._tabs[tab_id]["info"] = info
        name = self._tabs[tab_id]["display_name"]
        display = f"{name} — {info}" if info else name
        self.tab_bar.update_tab_label(tab_id, display)
        if self.on_tab_info_change:
            self.on_tab_info_change(tab_id, info)

    def _deactivate(self, tab_id: int):
        if tab_id not in self._tabs:
            return
        self._tabs[tab_id]["frame"].lower()
        fn = self._get_hook(tab_id, "on_unfocused")
        if fn:
            try:
                fn()
            except Exception:
                pass
        if self.on_tab_deactivate:
            self.on_tab_deactivate(tab_id)

    def _call_configure_menu(self, tab_id: int):
        """Call configure_menu on the active tab's per-tab namespace.

        Supports both new signature (tabmanager) and old signature (menubar)
        for backwards compatibility.
        """
        cfg = self._get_hook(tab_id, "configure_menu")
        if cfg is None:
            return
        try:
            sig = inspect.signature(cfg)
            params = list(sig.parameters.keys())
            if params and params[0] == "menubar":
                if self._menubar:
                    cfg(self._menubar)
            else:
                cfg(self)
        except Exception:
            pass

    def _on_focus_change(self, tab_id: int | None):
        prev = self._active
        if prev is not None and prev != tab_id:
            self._deactivate(prev)

        self._active = tab_id

        if tab_id is not None and tab_id in self._tabs:
            self._tabs[tab_id]["frame"].lift()
            fn = self._get_hook(tab_id, "on_focused")
            if fn:
                try:
                    fn()
                except Exception:
                    pass
            if self.on_tab_activate:
                self.on_tab_activate(tab_id, self._tabs[tab_id].get("module"))
        elif tab_id is None and self.on_tab_deactivate:
            self.on_tab_deactivate(None)

    def _on_close_request(self, tab_id: int):
        entry = self._tabs.get(tab_id)
        if entry is None:
            return
        fn = self._get_hook(tab_id, "has_unsaved")
        if fn:
            try:
                if fn():
                    from tkinter import messagebox
                    if not messagebox.askyesno(
                        "Close tab",
                        f'"{entry["display_name"]}" has unsaved changes.\nClose anyway?',
                    ):
                        return
            except Exception:
                pass
        self.close_tab(tab_id)

    def _on_popout_request(self, tab_id: int):
        if self.on_tab_popout:
            self.on_tab_popout(tab_id)

    def _on_refresh_request(self, tab_id: int):
        if self.on_tab_refresh:
            self.on_tab_refresh(tab_id)
        else:
            self.force_refresh_tab(tab_id)

    def _on_detach_request(self, tab_id: int):
        if self.on_tab_detach:
            self.on_tab_detach(tab_id)

    def _on_split_request(self, tab_id: int, direction: str, target_pane=None):
        if self.on_tab_split:
            self.on_tab_split(tab_id, direction, target_pane)

    def _on_merge_request(self, tab_id: int, source_bar: "TabBar",
                          insert_idx: int = -1):
        """A drag from *source_bar* was released over this bar at *insert_idx*.

        Uses :meth:`move_tab` so the per-tab namespace and in-tab state
        survive the merge.
        """
        source_mgr = source_bar.owner
        if source_mgr is None or source_mgr is self:
            return
        if not source_mgr.has_tab(tab_id):
            return
        self.move_tab(source_mgr, tab_id, insert_idx=insert_idx)
