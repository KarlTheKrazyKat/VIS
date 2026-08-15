"""Built-in application settings surface (0.6.0; tab mode 0.6.x).

The settings UI is a ``ttk.Notebook`` whose first tab ("General") edits the
framework's window / host / appearance / notification preferences stored in
:attr:`Project.Settings`.  Additional tabs are contributed by the application
via :meth:`Host.register_settings_panel(name, setup_fn)
<VIStk.Objects._Host.Host.register_settings_panel>`.

Two hosts render that same surface, sharing :class:`_SettingsUI`:

* :class:`SettingsTab` — a built-in *tab module* (duck-typed like a screen:
  ``setup(frame)`` / ``on_quit()``).  This is what :meth:`Host._open_settings`
  now opens, so Settings lives in the tab strip like any screen rather than a
  separate modal window.  ``setup`` may run more than once (a tab can be
  dragged between panes), so it rebuilds from scratch each time, re-seeding
  every control from :attr:`Project.Settings`.

* :class:`SettingsWindow` — the original modal ``tk.Toplevel``.  Retained as a
  fallback for the (rare) case where there is no chromed window to host a tab,
  and for any external caller that still constructs it directly.

Values are seeded from :meth:`ProjectSettings.effective` so every control shows
its current effective value (default or override).  On **Save**, a control
whose value equals the framework default is written as a *reset* (no redundant
override) so ``settings.json`` stays minimal; the rest are stored and flushed
with a single :meth:`ProjectSettings.save`.

Appearance settings are persisted but applied on next launch (live restyling is
deferred — see the 0.6.1 changelog entry).
"""
from __future__ import annotations

import inspect
import sys
import tkinter as tk
from tkinter import ttk
from tkinter import font as tkfont

from VIStk.Objects._WindowGeometry import WindowGeometry


_ALIGN_CHOICES = ["center", "n", "ne", "e", "se", "s", "sw", "w", "nw"]


class _SettingsUI:
    """Shared builder + persistence for the settings surface.

    Mixed into both :class:`SettingsTab` and :class:`SettingsWindow`.  A host
    class must call :meth:`_init_settings_state` before building, then
    :meth:`_build_notebook` to create the tabbed body, and :meth:`_persist` /
    :meth:`_restore_defaults` for the action buttons.
    """

    # ── State ─────────────────────────────────────────────────────────────────

    def _init_settings_state(self, host) -> None:
        """Seed the host reference, settings store, and the read-back registry.

        Safe to call again to rebuild (e.g. a tab moved between panes): it
        clears ``_vars`` so a fresh build re-seeds every control from the
        current stored values rather than reusing stale variables.
        """
        self.host = host
        self.Settings = host.Project.Settings
        # key -> (tk variable, value-type) for read-back on Save.
        self._vars: dict[str, tuple[tk.Variable, type]] = {}

    # ── Content ───────────────────────────────────────────────────────────────

    def _build_notebook(self, parent) -> ttk.Notebook:
        """Build the General tab plus every developer-registered panel."""
        nb = ttk.Notebook(parent)

        general = ttk.Frame(nb, padding=12)
        nb.add(general, text="General")
        self._build_general(general)

        # Developer-registered panels become additional tabs.  Each setup_fn
        # receives the tab frame and builds into it (mirrors screen setup()).
        # A failing panel shows an inline error in its tab rather than a
        # blank one (mirrors TabManager's screen-setup error handling).
        for name, setup_fn in getattr(self.host, "_settings_panels", {}).items():
            frame = ttk.Frame(nb, padding=12)
            nb.add(frame, text=name)
            try:
                # A panel may take just the frame (self-managed persistence)
                # or (frame, ui) to build fields that ride this window's own
                # Save / Restore Defaults via the add_* helpers below.
                if self._accepts_two(setup_fn):
                    setup_fn(frame, self)
                else:
                    setup_fn(frame)
            except Exception as e:
                import traceback
                traceback.print_exc()
                ttk.Label(frame, text=f"Error loading this panel:\n{e}",
                          foreground="red", justify="left",
                          wraplength=380).pack(anchor="w", pady=8)
        return nb

    @staticmethod
    def _accepts_two(fn) -> bool:
        """True if *fn* can be called with two positional args (frame, ui)."""
        try:
            sig = inspect.signature(fn)
        except (TypeError, ValueError):
            return False
        positional = 0
        for p in sig.parameters.values():
            if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD):
                positional += 1
            elif p.kind == p.VAR_POSITIONAL:
                return True
        return positional >= 2

    # ── Public field builders (for registered panels' (frame, ui) form) ────────
    # These register the control in this window's read-back registry, so a
    # panel built with them is saved, restored, and defaulted exactly like the
    # General tab — no per-panel Save button, no apply-on-change surprise.

    def add_check(self, parent, row: int, label: str, key: str):
        """A checkbox bound to boolean setting *key*."""
        return self._row_check(parent, row, label, key)

    def add_int(self, parent, row: int, label: str, key: str, hint: str = ""):
        """A spinbox bound to integer setting *key* (blank = unset/default)."""
        return self._row_int(parent, row, label, key, hint)

    def add_combo(self, parent, row: int, label: str, key: str, values,
                  editable: bool = False):
        """A combobox bound to string setting *key*."""
        return self._row_combo(parent, row, label, key, values, editable)

    def _build_general(self, parent) -> None:
        parent.columnconfigure(0, weight=1)

        win = ttk.LabelFrame(parent, text="Window & display", padding=10)
        win.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        self._row_int(win, 0, "Default width", "window.default_width", "px (blank = 1200)")
        self._row_int(win, 1, "Default height", "window.default_height", "px (blank = 800)")
        self._row_int(win, 2, "Minimum width", "window.min_width", "px (blank = none)")
        self._row_int(win, 3, "Minimum height", "window.min_height", "px (blank = none)")
        self._row_combo(win, 4, "Alignment", "window.default_align", _ALIGN_CHOICES)
        self._row_check(win, 5, "Remember last window size & position",
                        "window.remember_geometry")
        self._row_check(win, 6, "Open maximized on launch",
                        "window.fullscreen_on_launch")

        host = ttk.LabelFrame(parent, text="Host & startup", padding=10)
        host.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        cb = self._row_check(host, 0, "Start with operating system",
                             "host.start_with_os")
        if sys.platform != "win32":
            cb.configure(state="disabled")
            ttk.Label(host, text="(Windows only)", foreground="grey").grid(
                row=0, column=2, sticky="w", padx=(6, 0))
        self._row_check(host, 1, "Reopen last session's tabs on launch",
                        "host.remember_tabs")

        app = ttk.LabelFrame(parent, text="Appearance", padding=10)
        app.grid(row=2, column=0, sticky="ew", pady=(0, 8))
        families = sorted(set(tkfont.families()))
        self._row_combo(app, 0, "Default font family", "appearance.font_family",
                        families, editable=True)
        self._row_int(app, 1, "Default font size", "appearance.font_size",
                      "pt (blank = default)")
        self._build_palette_row(app, 2)
        self._build_tab_style_row(app, 3)
        ttk.Label(app, text="Font changes apply on next launch; palette and "
                  "tab style apply immediately.", foreground="grey").grid(
                      row=4, column=0, columnspan=3, sticky="w", pady=(4, 0))

        note = ttk.LabelFrame(parent, text="Notifications", padding=10)
        note.grid(row=3, column=0, sticky="ew")
        self._row_check(note, 0, "Enable notifications", "notifications.enabled")
        self._row_int(note, 1, "Notification duration", "notifications.duration_ms", "ms")

    def _build_palette_row(self, parent, row: int) -> None:
        """The Colour-palette dropdown — offered names come from the app's
        curated list (``offer_palettes``), plus ``system`` (follow the OS) and
        a blank entry meaning "the app's default".  Selecting one applies live
        so the user sees it on every open window before saving."""
        choices = ["", "system"] + [n for n in self.host.Project.offeredPalettes()
                                    if n != "system"]
        cb = self._row_combo(parent, row, "Colour palette",
                             "appearance.color_scheme", choices)
        var = self._vars["appearance.color_scheme"][0]
        cb.bind("<<ComboboxSelected>>",
                lambda e: self._preview_palette(var.get()))
        ttk.Label(parent, text="(blank = app default)", foreground="grey").grid(
            row=row, column=2, sticky="w", padx=(6, 0))

    def _preview_palette(self, name: str) -> None:
        """Apply *name* live to every open bar (persisted on Save).

        A blank pick means "no override", so the preview shows the app's own
        default — the same thing Save will resolve to.
        """
        try:
            self.host.Project.setActivePalette(name or None)
            self.host._watch_system_theme()
        except Exception:
            pass

    def _build_tab_style_row(self, parent, row: int) -> None:
        """The Tab-style dropdown — offered names come from the app's curated
        list (``TabBar.offer_styles``); selecting one applies live so the user
        sees it on every open window before saving."""
        from VIStk.Widgets import TabBar
        offered = TabBar.offered_styles()
        cb = self._row_combo(parent, row, "Tab style", "appearance.tab_style",
                             offered)
        var = self._vars["appearance.tab_style"][0]
        if not var.get():
            # No stored override yet — show the app's default as the selection.
            var.set(TabBar.default_style())
        cb.bind("<<ComboboxSelected>>",
                lambda e: self._preview_tab_style(var.get()))

    def _preview_tab_style(self, name: str) -> None:
        """Apply *name* live to every open tab bar (persisted on Save).

        No scheme is passed, so the style resolves against whatever palette is
        currently active — including one previewed from the row above but not
        yet saved.
        """
        try:
            from VIStk.Widgets import TabBar
            TabBar.set_tab_style(name)
        except Exception:
            pass

    # ── Row helpers ───────────────────────────────────────────────────────────

    def _var(self, key: str, vartype: type) -> tk.Variable:
        """Create and register a Tk variable seeded from the effective value."""
        val = self.Settings.get(key)
        if vartype is bool:
            var: tk.Variable = tk.BooleanVar(value=bool(val))
        else:
            var = tk.StringVar(value="" if val is None else str(val))
        self._vars[key] = (var, vartype)
        return var

    def _row_check(self, parent, r: int, label: str, key: str):
        var = self._var(key, bool)
        cb = ttk.Checkbutton(parent, text=label, variable=var)
        cb.grid(row=r, column=0, columnspan=2, sticky="w", pady=2)
        return cb

    def _row_int(self, parent, r: int, label: str, key: str, hint: str = ""):
        var = self._var(key, int)
        ttk.Label(parent, text=label + ":").grid(row=r, column=0, sticky="w", pady=2)
        sp = ttk.Spinbox(parent, from_=0, to=99999, textvariable=var, width=10)
        sp.grid(row=r, column=1, sticky="w", padx=(6, 0))
        if hint:
            ttk.Label(parent, text=hint, foreground="grey").grid(
                row=r, column=2, sticky="w", padx=(6, 0))
        return sp

    def _row_combo(self, parent, r: int, label: str, key: str, values,
                   editable: bool = False):
        var = self._var(key, str)
        ttk.Label(parent, text=label + ":").grid(row=r, column=0, sticky="w", pady=2)
        cb = ttk.Combobox(parent, textvariable=var, values=list(values), width=18,
                          state="normal" if editable else "readonly")
        cb.grid(row=r, column=1, sticky="w", padx=(6, 0))
        return cb

    # ── Persistence ───────────────────────────────────────────────────────────

    def _coerce(self, key: str, var: tk.Variable, vartype: type):
        """Convert a widget value to its stored form.

        ``int`` fields: blank -> ``None``; non-numeric -> keep the current
        stored value (reject bad input silently rather than corrupt it).
        ``str`` fields: blank -> ``None``.  ``bool``: as-is.
        """
        raw = var.get()
        if vartype is bool:
            return bool(raw)
        s = str(raw).strip()
        if vartype is int:
            if not s:
                return None
            try:
                n = int(s)
            except ValueError:
                return self.Settings.get(key)
            # Reject negatives (Spinbox from_=0 only constrains the arrows,
            # not typed input) — fall back to the default for these fields.
            return n if n >= 0 else None
        return s if s else None

    def _persist(self) -> None:
        """Write every control's value into ``Project.Settings`` and flush.

        Keeps ``settings.json`` minimal: a value equal to the framework
        default is stored as a *reset* rather than a redundant override.
        """
        for key, (var, vartype) in self._vars.items():
            # The start-with-OS control is disabled (and meaningless) off
            # Windows; leave any stored value untouched so a non-Windows
            # session can't clobber a Windows preference.
            if key == "host.start_with_os" and sys.platform != "win32":
                continue
            value = self._coerce(key, var, vartype)
            if value == self.Settings.DEFAULTS.get(key):
                self.Settings.reset(key)
            else:
                self.Settings.set(key, value)

        self._apply_start_with_os()
        self.Settings.save()

    def _apply_start_with_os(self) -> None:
        """Reconcile the OS-startup registry entry with the toggle.

        ``_register_startup`` / ``unregister_startup`` are both idempotent and
        Windows-guarded, so acting on the new value each save is safe.
        """
        entry = self._vars.get("host.start_with_os")
        if entry is None:
            return
        try:
            if bool(entry[0].get()):
                self.host._register_startup()
            else:
                self.host.unregister_startup()
        except Exception:
            pass

    def _restore_defaults(self) -> None:
        """Reset every control to its framework default (not saved until Save)."""
        for key, (var, vartype) in self._vars.items():
            d = self.Settings.DEFAULTS.get(key)
            if vartype is bool:
                var.set(bool(d))
            else:
                var.set("" if d is None else str(d))


class SettingsTab(_SettingsUI):
    """Built-in *tab module* hosting the settings surface.

    Duck-typed like a screen so the Host/TabManager drive it uniformly: they
    call :meth:`setup` to build into the tab frame and :meth:`on_quit` on close.
    There is no ``loop`` — the surface is static once built.

    ``setup`` may be called more than once for one logical tab (VIStk re-runs
    it when a tab is dragged between panes); each call rebuilds and re-seeds
    from :attr:`Project.Settings`, so any unsaved edits are dropped on a move —
    the same "closing discards" contract as the modal window's Cancel.
    """

    #: Stable identity for single-instance focus (Host._find_tab_by_base).
    base_name = "Settings"

    def __init__(self, host):
        self._init_settings_state(host)
        self._status = None

    def setup(self, parent) -> None:
        self._init_settings_state(self.host)      # fresh vars, re-seeded

        body = ttk.Frame(parent)
        body.place(relx=0, rely=0, relwidth=1, relheight=1)

        nb = self._build_notebook(body)
        nb.pack(fill="both", expand=True, padx=8, pady=(8, 0))

        btns = ttk.Frame(body, padding=(8, 8))
        btns.pack(fill="x")
        ttk.Button(btns, text="Restore Defaults",
                   command=self._restore_defaults).pack(side="left")
        ttk.Button(btns, text="Save", command=self._save).pack(side="right")
        self._status = ttk.Label(btns, text="", foreground="grey")
        self._status.pack(side="right", padx=(0, 8))

    def _save(self) -> None:
        self._persist()
        if self._status is not None:
            self._status.config(text="Saved.")

    def on_quit(self) -> bool:
        """No veto — closing the tab simply discards any unsaved edits."""
        return True


class SettingsWindow(tk.Toplevel, _SettingsUI):
    """Modal, tabbed application-settings editor (legacy fallback).

    Retained for the case where :meth:`Host._open_settings` has no chromed
    window to host a :class:`SettingsTab`, and for any caller still building
    it directly.  Behaviour is unchanged from 0.6.0.
    """

    def __init__(self, host, parent=None):
        super().__init__(parent)
        self.withdraw()  # only the centred, fully-built window is ever shown
        self._init_settings_state(host)
        self.title(f"{host.Project.title} — Settings")

        nb = self._build_notebook(self)
        nb.pack(fill="both", expand=True, padx=8, pady=(8, 0))

        # ── Button row ────────────────────────────────────────────────────────
        btns = ttk.Frame(self, padding=(8, 8))
        btns.pack(fill="x")
        ttk.Button(btns, text="Cancel", command=self._cancel).pack(side="right")
        ttk.Button(btns, text="Save", command=self._save).pack(side="right", padx=(0, 6))
        ttk.Button(btns, text="Restore Defaults",
                   command=self._restore_defaults).pack(side="left")

        self.protocol("WM_DELETE_WINDOW", self._cancel)
        self.bind("<Escape>", lambda e: self._cancel())

        # ── Geometry (Dialogs pattern) ────────────────────────────────────────
        WindowGeometry(self)
        self.update_idletasks()
        self.minsize(440, 420)
        # Set transient while still withdrawn — before any deiconify — so the
        # modal stacking is established correctly on all window managers.
        if parent is not None:
            self.transient(parent)
        if parent is not None and int(parent.winfo_viewable()):
            self.WindowGeometry.center_on(parent)
        else:
            self.deiconify()

    def show(self) -> None:
        """Grab input and block until the window is closed (Save/Cancel)."""
        self.grab_set()
        self.wait_window()

    def _save(self) -> None:
        self._persist()
        self._close()

    def _cancel(self) -> None:
        self._close()

    def _close(self) -> None:
        try:
            self.grab_release()
        except tk.TclError:
            pass
        self.destroy()
