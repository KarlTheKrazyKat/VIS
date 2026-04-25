"""DateEntry widget (0.5.0).

A date input widget with format validation and an optional calendar
picker popup, with no third-party dependencies.

Usage::

    from VIStk.Widgets import DateEntry
    de = DateEntry(parent, date_format="%Y-%m-%d")
    de.pack()

    de.get()                 # -> datetime.date | None
    de.set(date(2026, 4, 23))
    de.var.get()             # -> "2026-04-23"

The widget is a small composite: a :class:`ttk.Entry` for direct typing
plus a calendar button that pops up a month grid.  Typing into the
entry is validated against ``date_format`` on focus-out; an invalid
string is reverted to the last valid value (or cleared if none).
"""

from __future__ import annotations

import calendar
import tkinter as tk
from datetime import date, datetime
from tkinter import ttk
from typing import Callable

from VIStk.Objects._WindowGeometry import WindowGeometry


class DateEntry(ttk.Frame):
    """Entry + calendar-picker for selecting a date."""

    _CAL_ICON = "☰"   # ☰ — kept ASCII-safe; users can override

    def __init__(self, master, *,
                 date_format: str = "%Y-%m-%d",
                 initial: date | None = None,
                 on_change: Callable[[date | None], None] | None = None,
                 entry_width: int | None = None,
                 **kwargs):
        """
        Args:
            date_format:  ``strftime``/``strptime`` pattern.  Default
                          ``"%Y-%m-%d"``.
            initial:      Optional starting date.
            on_change:    Optional callback fired with the new
                          ``date | None`` whenever the value changes via
                          the entry, the picker, or :meth:`set`.
            entry_width:  Width passed to the inner ``ttk.Entry``.
                          Defaults to ``len(today.strftime(fmt)) + 2``.
            **kwargs:     Forwarded to :class:`ttk.Frame`.
        """
        super().__init__(master, **kwargs)
        self._fmt = date_format
        self._on_change = on_change
        self._last_valid: date | None = initial
        self._popup: tk.Toplevel | None = None

        if entry_width is None:
            entry_width = len(date.today().strftime(self._fmt)) + 2

        self.var = tk.StringVar(value=initial.strftime(self._fmt) if initial else "")
        """``StringVar`` holding the entry text.  Mutating it directly
        bypasses validation; prefer :meth:`set`."""

        self._entry = ttk.Entry(self, textvariable=self.var, width=entry_width)
        self._entry.pack(side="left", fill="x", expand=True)
        self._entry.bind("<FocusOut>", self._on_entry_commit, add="+")
        self._entry.bind("<Return>",   self._on_entry_commit, add="+")

        self._btn = ttk.Button(self, text=self._CAL_ICON, width=3,
                               command=self._open_picker)
        self._btn.pack(side="left", padx=(2, 0))

        self.bind("<Destroy>", lambda e: self._close_picker(), add="+")

    # ── Public API ─────────────────────────────────────────────────────────

    def get(self) -> date | None:
        """Return the current date, or ``None`` when the field is empty
        / invalid."""
        text = self.var.get().strip()
        if not text:
            return None
        try:
            return datetime.strptime(text, self._fmt).date()
        except ValueError:
            return None

    def set(self, value: date | None) -> None:
        """Set the date programmatically.  ``None`` clears the field."""
        self._last_valid = value
        self.var.set(value.strftime(self._fmt) if value else "")
        self._fire_change(value)

    # ── Entry validation ───────────────────────────────────────────────────

    def _on_entry_commit(self, _event=None):
        text = self.var.get().strip()
        if not text:
            if self._last_valid is not None:
                self._last_valid = None
                self._fire_change(None)
            return
        try:
            parsed = datetime.strptime(text, self._fmt).date()
        except ValueError:
            # Revert to last valid value.
            self.var.set(self._last_valid.strftime(self._fmt)
                         if self._last_valid else "")
            return
        if parsed != self._last_valid:
            self._last_valid = parsed
            self._fire_change(parsed)
        # Re-canonicalise the displayed text (e.g. zero-pad).
        self.var.set(parsed.strftime(self._fmt))

    def _fire_change(self, value: date | None) -> None:
        if self._on_change is None:
            return
        try:
            self._on_change(value)
        except Exception:
            pass

    # ── Calendar picker ────────────────────────────────────────────────────

    def _open_picker(self) -> None:
        if self._popup is not None and bool(self._popup.winfo_exists()):
            self._close_picker()
            return

        seed = self.get() or date.today()
        self._popup = tk.Toplevel(self)
        self._popup.withdraw()
        self._popup.overrideredirect(True)
        self._popup.attributes("-topmost", True)

        self._cal_year = seed.year
        self._cal_month = seed.month
        self._cal_selected = seed if self.get() is not None else None

        self._build_calendar()

        # Position just below the entry; nudge up if it would clip.
        self._popup.update_idletasks()
        x = self._entry.winfo_rootx()
        y = self._entry.winfo_rooty() + self._entry.winfo_height() + 2
        self._popup.geometry(f"+{x}+{y}")
        self._popup.deiconify()

        # Close popup on click outside.
        self._popup.bind("<FocusOut>", self._on_popup_focus_out, add="+")
        self._popup.focus_set()

    def _close_picker(self) -> None:
        if self._popup is not None:
            try:
                self._popup.destroy()
            except tk.TclError:
                pass
        self._popup = None

    def _on_popup_focus_out(self, _event):
        # Defer so click-on-button doesn't bounce open.
        self._popup.after(50, self._maybe_close)

    def _maybe_close(self):
        if self._popup is None:
            return
        try:
            f = self._popup.focus_displayof()
        except tk.TclError:
            f = None
        if f is None or str(f).startswith(str(self._popup)) is False:
            self._close_picker()

    def _build_calendar(self) -> None:
        for child in list(self._popup.children.values()):
            child.destroy()

        outer = ttk.Frame(self._popup, padding=4, relief="solid", borderwidth=1)
        outer.pack(fill="both", expand=True)

        # Header row: ◀ / Month YYYY / ▶
        hdr = ttk.Frame(outer)
        hdr.pack(fill="x")
        ttk.Button(hdr, text="◀", width=3,
                   command=lambda: self._shift_month(-1)).pack(side="left")
        month_label = f"{calendar.month_name[self._cal_month]} {self._cal_year}"
        ttk.Label(hdr, text=month_label, anchor="center").pack(
            side="left", fill="x", expand=True, padx=4)
        ttk.Button(hdr, text="▶", width=3,
                   command=lambda: self._shift_month(+1)).pack(side="left")

        # Day-of-week row.
        dow = ttk.Frame(outer)
        dow.pack(fill="x")
        for i, name in enumerate(["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]):
            ttk.Label(dow, text=name, anchor="center", width=4).grid(
                row=0, column=i, padx=1, pady=1)

        # Day grid — calendar.monthcalendar returns weeks of length 7,
        # zero-padded to align with Mon-first.
        grid = ttk.Frame(outer)
        grid.pack(fill="both", expand=True)
        weeks = calendar.Calendar(firstweekday=0).monthdayscalendar(
            self._cal_year, self._cal_month)
        for r, week in enumerate(weeks):
            for c, day in enumerate(week):
                if day == 0:
                    ttk.Label(grid, text="", width=4).grid(
                        row=r, column=c, padx=1, pady=1)
                    continue
                d = date(self._cal_year, self._cal_month, day)
                style = "Toolbutton"
                btn = ttk.Button(grid, text=str(day), width=4, style=style,
                                 command=lambda dd=d: self._pick(dd))
                btn.grid(row=r, column=c, padx=1, pady=1)
                if self._cal_selected == d:
                    btn.state(["pressed"])
                if d == date.today():
                    btn.configure(text=f"[{day}]")

    def _shift_month(self, delta: int) -> None:
        m = self._cal_month + delta
        y = self._cal_year
        while m < 1:
            m += 12; y -= 1
        while m > 12:
            m -= 12; y += 1
        self._cal_month = m
        self._cal_year = y
        self._build_calendar()

    def _pick(self, d: date) -> None:
        self.set(d)
        self._close_picker()
