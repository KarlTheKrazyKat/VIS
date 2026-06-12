import json
import os


_UNSET = object()


class ProjectSettings:
    """Per-project application settings, persisted to ``.VIS/settings.json``.

    Obtained via :attr:`Project.Settings` rather than constructed directly.
    Settings are flat ``key -> value`` pairs; keys use a dotted convention
    for grouping (``"window.min_width"``, ``"appearance.font_family"``) but
    are treated as opaque strings.

    The on-disk file holds **overrides only** — keys whose values differ
    from (or were explicitly written over) the framework :data:`DEFAULTS`.
    A project that has never saved a setting has no ``settings.json`` at all;
    :meth:`get` still resolves every known key through :data:`DEFAULTS`.

    Reads and writes are in-memory until :meth:`save` is called.  The Host
    saves automatically on shutdown (see ``Host.quit_host`` /
    ``Host._quit_if_no_windows``); other callers must call :meth:`save`
    themselves.  The file is wholly owned by this object (unlike
    ``project.json``, which is shared with screens/groups), so :meth:`save`
    rewrites it from the in-memory store without a read-merge.
    """

    #: Framework default for every known setting.  ``get(key)`` with no
    #: explicit default falls back to this table; an explicit ``default``
    #: argument takes precedence over it.  Keys absent here are unknown and
    #: resolve to ``None`` (or the caller's explicit default).
    #:
    #: Values MUST be immutable (``None`` / ``bool`` / ``int`` / ``str``):
    #: :meth:`get` and :meth:`effective` hand back the default object by
    #: reference, so a mutable default (e.g. ``[]``) could be mutated in
    #: place by a caller and corrupt every later read.  Represent "empty
    #: list" defaults as ``None`` and let callers coalesce (``... or []``).
    DEFAULTS: dict = {
        # ── Window & display ──────────────────────────────────────────────
        "window.default_width": None,
        "window.default_height": None,
        "window.default_align": None,        # 'center' | compass dir | None
        "window.min_width": None,
        "window.min_height": None,
        "window.remember_geometry": False,
        "window.fullscreen_on_launch": False,
        "window.last_geometry": None,        # framework-written: 'WxH+X+Y'
        # ── Host & startup ────────────────────────────────────────────────
        "host.start_with_os": False,
        "host.remember_tabs": False,
        "host.last_tabs": None,              # framework-written: [base_name]
        # ── Appearance ────────────────────────────────────────────────────
        "appearance.font_family": None,      # None → platform default
        "appearance.font_size": None,        # None → widget default
        "appearance.color_scheme": "system",  # placeholder for styles system
        # ── Notifications ─────────────────────────────────────────────────
        "notifications.enabled": True,
        "notifications.duration_ms": 5000,
    }

    def __init__(self, project):
        self.project = project
        self.path: str = project.p_settings
        self._store: dict = {}
        self._loaded: bool = False
        self._dirty: bool = False  # True once an override actually changes

    @property
    def dirty(self) -> bool:
        """True when an override has changed since the last :meth:`save`.

        The Host's shutdown flush consults this to avoid rewriting
        ``settings.json`` (and bumping its mtime) when nothing changed.
        """
        return self._dirty

    # ── Loading ───────────────────────────────────────────────────────────

    def _ensure_loaded(self) -> None:
        """Read ``settings.json`` on first access.

        A missing file is normal (no overrides yet).  A corrupt or
        unreadable file is non-fatal: warn to stderr and fall back to an
        empty store so the app still launches on framework defaults.
        """
        if self._loaded:
            return
        self._loaded = True
        if not os.path.exists(self.path):
            return
        try:
            with open(self.path, "r") as f:
                data = json.load(f)
            if isinstance(data, dict):
                self._store = data
            else:
                self._warn("settings.json is not a JSON object; ignoring.")
        except (json.JSONDecodeError, OSError) as e:
            self._warn(f"could not read settings.json ({e}); using defaults.")

    @staticmethod
    def _warn(msg: str) -> None:
        import sys
        print(f"[VIStk] ProjectSettings: {msg}", file=sys.stderr)

    # ── Read / write ──────────────────────────────────────────────────────

    def get(self, key: str, default=_UNSET):
        """Return the value for ``key``.

        Resolution order: stored override → explicit ``default`` argument
        (when given) → framework :data:`DEFAULTS` → ``None``.
        """
        self._ensure_loaded()
        if key in self._store:
            return self._store[key]
        if default is not _UNSET:
            return default
        return self.DEFAULTS.get(key)

    def set(self, key: str, value) -> None:
        """Set ``key`` in memory.  Call :meth:`save` to persist."""
        self._ensure_loaded()
        if self._store.get(key, _UNSET) != value:
            self._dirty = True
        self._store[key] = value

    def reset(self, key: str) -> None:
        """Drop the override for ``key`` so it resolves back to its default."""
        self._ensure_loaded()
        if key in self._store:
            self._dirty = True
            del self._store[key]

    def __contains__(self, key: str) -> bool:
        self._ensure_loaded()
        return key in self._store

    def effective(self) -> dict:
        """The full resolved settings map (``DEFAULTS`` merged with overrides).

        Intended for the Settings UI, which needs current values for every
        known key regardless of whether the user has overridden them.
        """
        self._ensure_loaded()
        return {**self.DEFAULTS, **self._store}

    # ── Persistence ───────────────────────────────────────────────────────

    def save(self) -> bool:
        """Write the in-memory overrides to ``.VIS/settings.json``.

        Returns ``True`` on success.  Writes nothing and returns ``False``
        if the project directory can't be written (reported to stderr) so a
        failed save never crashes the shutdown path.
        """
        self._ensure_loaded()
        try:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            with open(self.path, "w") as f:
                json.dump(self._store, f, indent=4)
            self._dirty = False
            return True
        except OSError as e:
            self._warn(f"could not write settings.json ({e}).")
            return False
