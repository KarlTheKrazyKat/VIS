import json
import os


_UNSET = object()

#: Schema version stamped into ``settings.json``.  Bumped when a stored value
#: changes meaning, so :meth:`ProjectSettings._migrate` can fix files written
#: by an older VIStk.  A file with no stamp is pre-1 (VIStk ≤ 0.6.4).
SCHEMA_VERSION = 1


class ProjectSettings:
    """Per-project application settings, persisted to ``.VIS/settings.json``.

    Obtained via :attr:`Project.Settings` rather than constructed directly.
    Settings are flat ``key -> value`` pairs; keys use a dotted convention
    for grouping (``"window.min_width"``, ``"appearance.font_family"``) but
    are treated as opaque strings.

    On first run a default ``settings.json`` is written with the full set of
    (default-valued) settings via :meth:`ensure_file`, so every available
    option is visible and hand-editable.  In memory only genuine *overrides*
    are tracked — values that differ from the framework :data:`DEFAULTS` — so
    :meth:`reset` and ``in`` mean "explicitly customised".  :meth:`save`
    writes the complete resolved set back, keeping the file whole.  A missing
    or corrupt file falls back to the defaults without crashing.

    Reads and writes are in-memory until :meth:`save` is called.  The Host
    saves automatically on shutdown (see ``Host.quit_host`` /
    ``Host._quit_if_no_windows``); other callers must call :meth:`save`
    themselves.  The file is wholly owned by this object (unlike
    ``project.json``, which is shared with screens/groups).
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
        "appearance.color_scheme": None,      # None → app's default_palette; else a
                                             # registered palette name, or 'system'
                                             # to follow the OS light/dark setting
        "appearance.tab_style": None,        # None → app's default_style (TabBar.offer_styles)
        "appearance.ttk_theme": None,        # None → platform default (Windows: vista)
        # ── Notifications ─────────────────────────────────────────────────
        "notifications.enabled": True,
        "notifications.duration_ms": 5000,
        # ── Framework bookkeeping ─────────────────────────────────────────
        "settings.version": SCHEMA_VERSION,  # framework-written; drives _migrate
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
                # The file is the full default set; in memory keep only
                # genuine overrides (values differing from the default, plus
                # any unknown custom keys) so reset()/``in`` stay meaningful.
                self._store = {k: v for k, v in data.items()
                               if v != self.DEFAULTS.get(k)}
                self._migrate(data)
            else:
                self._warn("settings.json is not a JSON object; ignoring.")
        except (json.JSONDecodeError, OSError) as e:
            self._warn(f"could not read settings.json ({e}); using defaults.")

    def _migrate(self, raw: dict) -> None:
        """Bring a file written by an older VIStk up to :data:`SCHEMA_VERSION`.

        Runs once per load against the *raw* file contents, right after the
        store is built.  Marks the store dirty so the shutdown flush stamps the
        new version — until it does, this simply runs again next launch, which
        is harmless.

        **v0 → v1 (0.6.5)** — ``appearance.color_scheme`` was written into every
        generated ``settings.json`` as ``"system"`` while the setting did
        nothing (0.6.0–0.6.4).  In 0.6.5 that value means "follow the OS
        light/dark theme", which would silently override the app's own palette
        for a user who never chose anything.  A stored ``"system"`` from an
        unstamped file is therefore dropped, so the app default applies; a user
        who really wants it re-picks it and the stamp keeps that choice.
        """
        if int(raw.get("settings.version") or 0) >= SCHEMA_VERSION:
            return
        if self._store.get("appearance.color_scheme") == "system":
            del self._store["appearance.color_scheme"]
        self._dirty = True

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

    def ensure_file(self) -> bool:
        """Materialise the default ``settings.json`` if it doesn't exist yet.

        Writes the full resolved set (the framework defaults plus any
        overrides) so every available setting is visible and hand-editable.
        Idempotent — an existing file (including user edits) is never
        overwritten — and does **not** mark the store dirty.  Returns
        ``True`` when a file was created.  Never raises.

        Called once at Host startup (and at ``VIS new`` scaffolding) so a
        default settings file appears without the user opting in.
        """
        self._ensure_loaded()
        if os.path.exists(self.path):
            return False
        try:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            with open(self.path, "w") as f:
                json.dump(self.effective(), f, indent=4)
            return True
        except OSError as e:
            self._warn(f"could not create settings.json ({e}).")
            return False

    def save(self) -> bool:
        """Write the full resolved settings to ``.VIS/settings.json``.

        Writes :meth:`effective` (defaults merged with overrides) so the file
        stays complete and hand-editable.  Returns ``True`` on success;
        writes nothing and returns ``False`` if the directory can't be
        written (reported to stderr) so a failed save never crashes shutdown.
        """
        self._ensure_loaded()
        try:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            with open(self.path, "w") as f:
                json.dump(self.effective(), f, indent=4)
            self._dirty = False
            return True
        except OSError as e:
            self._warn(f"could not write settings.json ({e}).")
            return False
