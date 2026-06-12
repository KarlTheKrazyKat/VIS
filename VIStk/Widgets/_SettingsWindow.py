"""Built-in application settings window (0.6.0).

A modal, tabbed dialog opened from **HostMenu -> Settings**.  The first tab
("General") edits the framework's window / host / appearance / notification
preferences stored in :attr:`Project.Settings`.  Additional tabs are
contributed by the application via
:meth:`Host.register_settings_panel(name, setup_fn) <VIStk.Objects._Host.Host.register_settings_panel>`.

Follows the modal pattern of :mod:`VIStk.Widgets._Dialogs`: build hidden,
centre on the parent window without flicker, grab input, and block in
``wait_window`` until Save or Cancel.

Values are seeded from :meth:`ProjectSettings.effective` so every control
shows its current effective value (default or override).  On **Save**, a
control whose value equals the framework default is written as a *reset*
(no redundant override) so ``settings.json`` stays minimal; the rest are
stored and flushed with a single :meth:`ProjectSettings.save`.

Appearance settings are persisted but applied on next launch (live
restyling is deferred — see the 0.6.1 changelog entry).
"""
from __future__ import annotations

import sys
import tkinter as tk
from tkinter import ttk
from tkinter import font as tkfont

from VIStk.Objects._WindowGeometry import WindowGeometry


_ALIGN_CHOICES = ["center", "n", "ne", "e", "se", "s", "sw", "w", "nw"]
_SCHEME_CHOICES = ["system", "light", "dark"]


class SettingsWindow(tk.Toplevel):
    """Modal, tabbed application-settings editor."""

    def __init__(self, host, parent=None):
        super().__init__(parent)
        self.withdraw()  # only the centred, fully-built window is ever shown
        self.host = host
        self.Settings = host.Project.Settings
        self.title(f"{host.Project.title} — Settings")

        # key -> (tk variable, value-type) for read-back on Save.
        self._vars: dict[str, tuple[tk.Variable, type]] = {}

        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=8, pady=(8, 0))

        general = ttk.Frame(nb, padding=12)
        nb.add(general, text="General")
        self._build_general(general)

        # Developer-registered panels become additional tabs.  Each setup_fn
        # receives the tab frame and builds into it (mirrors screen setup()).
        # A failing panel shows an inline error in its tab rather than a
        # blank one (mirrors TabManager's screen-setup error handling).
        for name, setup_fn in getattr(host, "_settings_panels", {}).items():
            frame = ttk.Frame(nb, padding=12)
            nb.add(frame, text=name)
            try:
                setup_fn(frame)
            except Exception as e:
                import traceback
                traceback.print_exc()
                ttk.Label(frame, text=f"Error loading this panel:\n{e}",
                          foreground="red", justify="left",
                          wraplength=380).pack(anchor="w", pady=8)

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

    # ── Section builders ──────────────────────────────────────────────────────

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
        self._row_combo(app, 2, "Color scheme", "appearance.color_scheme",
                        _SCHEME_CHOICES)
        ttk.Label(app, text="Appearance changes apply on next launch.",
                  foreground="grey").grid(row=3, column=0, columnspan=3,
                                          sticky="w", pady=(4, 0))

        note = ttk.LabelFrame(parent, text="Notifications", padding=10)
        note.grid(row=3, column=0, sticky="ew")
        self._row_check(note, 0, "Enable notifications", "notifications.enabled")
        self._row_int(note, 1, "Notification duration", "notifications.duration_ms", "ms")

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

    # ── Actions ───────────────────────────────────────────────────────────────

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

    def _save(self) -> None:
        for key, (var, vartype) in self._vars.items():
            # The start-with-OS control is disabled (and meaningless) off
            # Windows; leave any stored value untouched so a non-Windows
            # session can't clobber a Windows preference.
            if key == "host.start_with_os" and sys.platform != "win32":
                continue
            value = self._coerce(key, var, vartype)
            # Keep settings.json minimal: store only genuine overrides.
            if value == self.Settings.DEFAULTS.get(key):
                self.Settings.reset(key)
            else:
                self.Settings.set(key, value)

        self._apply_start_with_os()
        self.Settings.save()
        self._close()

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

    def _cancel(self) -> None:
        self._close()

    def _close(self) -> None:
        try:
            self.grab_release()
        except tk.TclError:
            pass
        self.destroy()
