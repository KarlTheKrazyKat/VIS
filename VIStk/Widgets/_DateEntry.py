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
plus a calendar button that pops up a month grid, kept inside the window
the widget is in.  Typing into the entry is read on focus-out or Return --
``date_format`` first, then the short forms people type (``10/14`` for this
year, ``10/14/26``), the fields taken in the order ``date_format`` has them.
Text that still will not read as a date is left as typed and shown in red,
and ``on_invalid`` is told, so whoever is typing can see what is wrong and
fix it rather than have it quietly put back.

Two entries can make a range -- give the end one ``range_start``::

    start = DateEntry(parent)
    end = DateEntry(parent, range_start=start)

Either one's calendar then picks both: the first day clicked is the start and
the second the end, with the days between shaded, and both entries change
together once the end is picked.  While either entry is disabled the other's
calendar picks its own date alone.
"""

from __future__ import annotations

import calendar
import re
import tkinter as tk
from datetime import date, datetime
from tkinter import ttk
from typing import Callable

from PIL import Image, ImageDraw, ImageTk

from VIStk.Objects._WindowGeometry import WindowGeometry


def _calendar_icon(size: int = 16) -> ImageTk.PhotoImage:
    """A small calendar for the picker button: a page with a header band,
    two binder rings and a grid of days.

    Drawn rather than loaded, so the widget ships no image files, and drawn
    at four times the size and scaled down so its edges come out smooth.
    """
    u = 4 * size / 16                     # one pixel of the finished icon
    ink = (74, 79, 85, 255)
    img = Image.new("RGBA", (4 * size, 4 * size), (0, 0, 0, 0))
    pen = ImageDraw.Draw(img)
    pen.rounded_rectangle((1 * u, 3 * u, 15 * u, 15 * u), radius=2 * u,
                          outline=ink, width=round(1.4 * u))
    pen.rounded_rectangle((1 * u, 3 * u, 15 * u, 7 * u), radius=2 * u, fill=ink)
    pen.rectangle((1 * u, 5 * u, 15 * u, 6.5 * u), fill=ink)
    pen.rounded_rectangle((4 * u, 1 * u, 5.6 * u, 5 * u), radius=0.8 * u, fill=ink)
    pen.rounded_rectangle((10.4 * u, 1 * u, 12 * u, 5 * u), radius=0.8 * u, fill=ink)
    for row in range(2):
        for col in range(3):
            x, y = (3.5 + 3.5 * col) * u, (8.6 + 3 * row) * u
            pen.rectangle((x, y, x + 2 * u, y + 1.8 * u), fill=ink)
    return ImageTk.PhotoImage(img.resize((size, size), Image.LANCZOS))


class DateEntry(ttk.Frame):
    """Entry + calendar-picker for selecting a date."""

    #: Text colour of an entry that will not read as a date.
    INVALID_FG = "#cc0000"

    def __init__(self, master, *,
                 date_format: str = "%Y-%m-%d",
                 initial: date | None = None,
                 on_change: Callable[[date | None], None] | None = None,
                 on_invalid: Callable[[str], None] | None = None,
                 entry_width: int | None = None,
                 range_start: DateEntry | None = None,
                 **kwargs):
        """
        Args:
            date_format:  ``strftime``/``strptime`` pattern.  Default
                          ``"%Y-%m-%d"``.
            initial:      Optional starting date.
            on_change:    Optional callback fired with the new
                          ``date | None`` whenever the value changes via
                          the entry, the picker, or :meth:`set`.
            on_invalid:   Optional callback fired with the text when what
                          was typed will not read as a date.
            entry_width:  Width passed to the inner ``ttk.Entry``.
                          Defaults to ``len(today.strftime(fmt)) + 2``.
            range_start:  The entry holding the start of a range this one is
                          the end of.  The two then share a calendar that
                          picks both -- see the module docstring.
            **kwargs:     Forwarded to :class:`ttk.Frame`.
        """
        super().__init__(master, **kwargs)
        self._fmt = date_format
        self._on_change = on_change
        self._on_invalid = on_invalid
        self._last_valid: date | None = initial
        self._popup: tk.Toplevel | None = None
        self._range: tuple[DateEntry, DateEntry] | None = None
        if range_start is not None:
            self._range = range_start._range = (range_start, self)

        if entry_width is None:
            entry_width = len(date.today().strftime(self._fmt)) + 2

        self.var = tk.StringVar(value=initial.strftime(self._fmt) if initial else "")
        """``StringVar`` holding the entry text.  Mutating it directly
        bypasses validation; prefer :meth:`set`."""

        self._entry = ttk.Entry(self, textvariable=self.var, width=entry_width)
        self._entry.pack(side="left", fill="x", expand=True)
        self._entry.bind("<FocusOut>", self._on_entry_commit, add="+")
        self._entry.bind("<Return>",   self._on_entry_commit, add="+")

        #?Held on the widget: Tk keeps no reference of its own to an image,
        # and one that is garbage collected leaves the button blank.
        self._icon = _calendar_icon()
        self._btn = ttk.Button(self, image=self._icon, width=2,
                               command=self._open_picker)
        self._btn.pack(side="left", padx=(2, 0))

        self.bind("<Destroy>", lambda e: self._close_picker(), add="+")

    # ── Public API ─────────────────────────────────────────────────────────

    def get(self) -> date | None:
        """Return the current date, or ``None`` when the field is empty
        / invalid.  Short forms read the same as on commit -- see
        :meth:`_parse`."""
        text = self.var.get().strip()
        if not text:
            return None
        return self._parse(text)

    def set(self, value: date | None) -> None:
        """Set the date programmatically.  ``None`` clears the field."""
        self._store(value)
        self._fire_change(value)

    def _store(self, value: date | None) -> None:
        """Put *value* in the field without telling anyone -- :meth:`set` does
        that after; a range sets both its ends first and tells after."""
        self._last_valid = value
        self._mark(False)
        self.var.set(value.strftime(self._fmt) if value else "")

    # ── Entry validation ───────────────────────────────────────────────────

    def _parse(self, text: str) -> date | None:
        """*text* as a date: ``date_format`` first, then the short forms.

        Two or three runs of digits split by ``/``, ``-`` or ``.``, taken in
        the order ``date_format`` puts month, day and year -- so with
        ``%m/%d/%Y`` ``10/14`` is the 14th of October this year and
        ``10/14/26`` the same day in 2026.  None when it is no date at all.
        """
        try:
            return datetime.strptime(text, self._fmt).date()
        except ValueError:
            pass
        parts = re.split(r"[/\-.]", text.strip())
        if len(parts) not in (2, 3) or not all(p.isdigit() for p in parts):
            return None
        order = sorted("mdY", key=lambda f: self._fmt.find("%" + f) % 100)
        if len(parts) == 2:
            order = [f for f in order if f != "Y"]
        fields = dict(zip(order, (int(p) for p in parts)))
        year = fields.get("Y", date.today().year)
        try:
            return date(year + 2000 if year < 100 else year, fields["m"], fields["d"])
        except ValueError:
            return None

    def _mark(self, bad: bool) -> None:
        """Show the entry's text in red while it will not read as a date."""
        self._entry.configure(foreground=self.INVALID_FG if bad else "")

    def _on_entry_commit(self, _event=None):
        text = self.var.get().strip()
        if not text:
            self._mark(False)
            if self._last_valid is not None:
                self._last_valid = None
                self._fire_change(None)
            return
        parsed = self._parse(text)
        if parsed is None:
            #?Left as typed and shown in red rather than put back to the last
            # good date: whoever typed it can see what is wrong and fix it.
            self._mark(True)
            if self._on_invalid is not None:
                try:
                    self._on_invalid(text)
                except Exception:
                    pass
            return
        self._mark(False)
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
        #?A range while both its ends can be set.  One held by something else
        # is disabled, and this entry's calendar then picks its own date alone.
        self._picking = (self._range if self._range is not None
                         and not any(end._entry.instate(["disabled"]) for end in self._range)
                         else None)
        self._first: date | None = None
        self._colours = self._palette()

        self._build_calendar()

        # The calendar stays inside the window the field is in (and on the
        # screen).  It opens below the entry and lined up with it, flips above
        # when there is no room below -- a field low in the window -- and is
        # pulled in from the right edge when the field sits close to it, as a
        # field in a side panel does.
        self._popup.update_idletasks()
        pw = self._popup.winfo_reqwidth()
        ph = self._popup.winfo_reqheight()
        win = self.winfo_toplevel()
        left = max(0, win.winfo_rootx())
        top = max(0, win.winfo_rooty())
        right = min(win.winfo_rootx() + win.winfo_width(), self._popup.winfo_screenwidth())
        bottom = min(win.winfo_rooty() + win.winfo_height(), self._popup.winfo_screenheight())
        ey = self._entry.winfo_rooty()
        below = ey + self._entry.winfo_height() + 2
        above = ey - ph - 2
        if below + ph <= bottom:
            y = below
        elif above >= top:
            y = above
        else:
            y = max(top, bottom - ph)
        x = max(left, min(self._entry.winfo_rootx(), right - pw))
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

        # The day names share the grid with the days, Sunday first, so each one
        # sits centred over its own column of boxes -- in a grid of their own
        # they lined up with nothing.
        grid = ttk.Frame(outer)
        grid.pack(fill="both", expand=True)
        for c, name in enumerate(("Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat")):
            grid.columnconfigure(c, uniform="day")
            ttk.Label(grid, text=name, anchor="center").grid(
                row=0, column=c, padx=1, pady=1, sticky="ew")

        # Day grid — monthdayscalendar returns weeks of length 7,
        # zero-padded to align with Sun-first.  Labels rather than ttk
        # buttons: a native button ignores colour, and a range is shaded.
        self._cells: dict[date, tk.Label] = {}
        weeks = calendar.Calendar(firstweekday=calendar.SUNDAY).monthdayscalendar(
            self._cal_year, self._cal_month)
        for r, week in enumerate(weeks, start=1):
            for c, day in enumerate(week):
                if day == 0:
                    continue
                d = date(self._cal_year, self._cal_month, day)
                cell = tk.Label(grid, text=f"[{day}]" if d == date.today() else str(day),
                                width=4, pady=3, cursor="hand2")
                cell.grid(row=r, column=c, padx=1, pady=1, sticky="ew")
                cell.bind("<Button-1>", lambda _e, dd=d: self._pick(dd))
                cell.bind("<Enter>", lambda _e, dd=d: self._paint(dd))
                cell.bind("<Leave>", lambda _e: self._paint())
                self._cells[d] = cell

        if self._picking is not None:
            self._hint = ttk.Label(outer, anchor="center")
            self._hint.pack(fill="x", pady=(4, 0))
        self._paint()

    def _palette(self) -> dict:
        """The calendar's colours: the app palette's own where it names them,
        the theme's otherwise, and tints of the selection colour for the days
        inside a range and the day under the pointer."""
        from VIStk.Styles import _theme
        style = ttk.Style()
        palette = _theme.current()

        def named(name, fallback):
            colour = palette.get(name) if palette is not None else None
            return colour or fallback

        #?The system's own selection colours, where Tk knows them by name --
        # ttk's vista theme reports an entry's selection as plain white.
        def system(name, fallback):
            try:
                self.winfo_rgb(name)
                return name
            except tk.TclError:
                return fallback
        surface = named("surface", style.lookup("TFrame", "background") or "SystemButtonFace")
        accent = named("selection", system("SystemHighlight", "#2f78d3"))

        def tint(share):
            pairs = zip(self.winfo_rgb(accent), self.winfo_rgb(surface))
            return "#" + "".join(f"{round((a * share + s * (1 - share)) / 257):02x}"
                                 for a, s in pairs)
        return {"surface": surface, "accent": accent, "range": tint(0.22), "hover": tint(0.12),
                "text": named("text", style.lookup("TLabel", "foreground") or "SystemButtonText"),
                "accent_text": named("selection_text", system("SystemHighlightText", "white"))}

    def _paint(self, hover: date | None = None) -> None:
        """Colour the days: the date chosen -- or a range's two ends and the
        days between -- and the day under the pointer.

        Once a range's start is picked, the range runs from it to the day under
        the pointer, so the end is seen before it is clicked.
        """
        if self._picking is None:
            low = high = self._cal_selected
        elif self._first is not None:
            low, high = sorted((self._first, hover or self._first))
        else:
            low, high = (end.get() for end in self._picking)
            low, high = low or high, high or low
        if self._picking is not None:
            self._hint.configure(text="Now pick the end date" if self._first is not None
                                 else "Pick the start date, then the end")
        colours = self._colours
        for d, cell in self._cells.items():
            if low is not None and d in (low, high):
                cell.configure(bg=colours["accent"], fg=colours["accent_text"])
            elif low is not None and low < d < high:
                cell.configure(bg=colours["range"], fg=colours["text"])
            else:
                cell.configure(bg=colours["hover"] if d == hover else colours["surface"],
                               fg=colours["text"])

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
        """A day clicked: this entry's date -- or, for a range, its start, and
        then its end, the two put in order and both ends set together."""
        if self._picking is None:
            self.set(d)
            self._close_picker()
            return
        if self._first is None:
            self._first = d
            self._paint(d)
            return
        low, high = sorted((self._first, d))
        start, end = self._picking
        start._store(low)
        end._store(high)
        start._fire_change(low)
        end._fire_change(high)
        self._close_picker()
