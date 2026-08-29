"""Tooltip widget (0.5.0).

Tkinter has no native tooltip.  ``Tooltip`` attaches one to any widget
with a single line::

    from VIStk.Widgets import Tooltip
    Tooltip(my_button, text="Save the current document")

Behaviour:

- Appears after a hover delay (default 500 ms).
- Disappears on ``<Leave>``, on click, on focus loss, and when the
  bound widget is destroyed.
- The popup itself never steals focus and is excluded from window
  manager decoration via ``overrideredirect``.
- ``text`` may be a plain ``str`` *or* a callable returning ``str`` —
  use the callable form for tooltips that change with state.
- Cleanly stops scheduling and hides the popup when the host widget is
  destroyed (no ``after`` callback leaks).
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable


class Tooltip:
    """Hover tooltip bound to a single widget."""

    def __init__(self, widget: tk.Widget, text: str | Callable[[], str],
                 *, delay_ms: int = 500,
                 wraplength: int = 240,
                 background: str | None = None,
                 foreground: str | None = None,
                 borderwidth: int = 1,
                 offset: tuple[int, int] = (0, 1),
                 anchor: str = "sw",
                 grace_ms: int = 250):
        """
        Args:
            widget:      The widget to attach to.
            text:        Tooltip text, or a zero-arg callable returning
                         the text (re-evaluated each time the tip is
                         shown — useful for state-dependent tooltips).
            delay_ms:    Hover delay before showing.  Default 500 ms.
            wraplength:  Pixel width at which the tooltip wraps.
            background:  Tooltip background colour.  ``None`` (the default)
                         follows the active theme's ``surface`` role, so the
                         tip is a light grey on a light theme and dark on a
                         dark one.  Pass an explicit colour to override.
            foreground:  Tooltip text colour.  ``None`` follows the theme's
                         ``text`` role.
            borderwidth: Border thickness in pixels.
            offset:      (x, y) nudge applied after anchoring, in pixels.  The
                         default drops the tip one pixel so its bottom border
                         clears the cursor hotspot instead of sharing that
                         pixel row with it.
            grace_ms:    How long the tip lingers after the pointer leaves the
                         widget, giving it time to reach the tip itself.  The
                         tip stays up for as long as the pointer is on it.
            anchor:      Which corner of the tip sits at the pointer -- one of
                         "nw", "ne", "sw", "se".  The default "sw" puts the
                         bottom-left corner on the cursor, so the tip rises
                         above the pointer and its left edge lines up with it.
                         "nw" is the older below-right placement.
        """
        self.widget = widget
        self._text = text
        self._delay_ms = delay_ms
        self._wraplength = wraplength
        self._bg = background
        self._fg = foreground
        self._bd = borderwidth
        self._offset = offset
        self._anchor = anchor
        self._grace_ms = grace_ms

        self._tip: tk.Toplevel | None = None
        self._after_id: str | None = None
        self._hide_id: str | None = None

        widget.bind("<Enter>",     self._on_enter,    add="+")
        widget.bind("<Leave>",     self._on_leave,    add="+")
        widget.bind("<ButtonPress>", self._on_leave,  add="+")
        widget.bind("<Destroy>",   self._on_destroy,  add="+")

    # ── Public mutators ────────────────────────────────────────────────────

    def set_text(self, text: str | Callable[[], str]) -> None:
        """Replace the tooltip text (or the callable producing it)."""
        self._text = text

    def hide(self) -> None:
        """Cancel any pending show or hide and destroy the popup if visible."""
        self._cancel()
        self._cancel_hide()
        self._destroy_tip()

    # ── Event handlers ─────────────────────────────────────────────────────

    def _on_enter(self, _event=None) -> None:
        #?Coming back onto the widget cancels a grace period already running,
        # so crossing the seam between widget and tip never flickers.
        self._cancel_hide()
        if self._tip is not None:
            return
        self._cancel()
        self._after_id = self.widget.after(self._delay_ms, self._show)

    def _on_leave(self, _event=None) -> None:
        """Start the grace period rather than hiding immediately.

        The pointer has to cross out of the widget to reach the tip -- with the
        default "sw" anchor the tip sits directly above the cursor, so moving
        onto it fires <Leave> here first.  Hiding at once would make the tip
        impossible to point at; instead it lingers briefly, and the tip's own
        <Enter> cancels the pending hide.
        """
        self._cancel()
        self._schedule_hide()

    def _on_destroy(self, _event=None) -> None:
        self.hide()

    # ── Internals ──────────────────────────────────────────────────────────

    def _schedule_hide(self) -> None:
        """Hide after the grace period unless something cancels it first."""
        self._cancel_hide()
        if self._tip is None:
            return
        try:
            self._hide_id = self.widget.after(self._grace_ms, self.hide)
        except tk.TclError:
            self._destroy_tip()

    def _cancel_hide(self) -> None:
        if self._hide_id is not None:
            try:
                self.widget.after_cancel(self._hide_id)
            except tk.TclError:
                pass
            self._hide_id = None

    def _cancel(self) -> None:
        if self._after_id is not None:
            try:
                self.widget.after_cancel(self._after_id)
            except tk.TclError:
                pass
            self._after_id = None

    @staticmethod
    def _role(name: str, fallback: str) -> str:
        """A theme colour by role name, or *fallback* when no theme is installed.

        Resolved per show rather than cached at construction, so a tip built
        before a theme switch still paints in the current theme.  Plain ``tk``
        widgets do not resolve role names themselves — only vWidgets and ttk
        styles do — so the lookup happens here.
        """
        try:
            from VIStk.Styles._theme import current
            palette = current()
            if palette is not None:
                return getattr(palette, name)
        except Exception:
            pass
        return fallback

    def _resolve_text(self) -> str:
        if callable(self._text):
            try:
                return str(self._text())
            except Exception:
                return ""
        return str(self._text)

    def _show(self) -> None:
        self._after_id = None
        text = self._resolve_text()
        if not text:
            return
        # Position relative to the cursor -- see the *offset* argument.
        try:
            px = self.widget.winfo_pointerx()
            py = self.widget.winfo_pointery()
        except tk.TclError:
            return
        tip = tk.Toplevel(self.widget)
        tip.withdraw()          # positioned once measured, so it never flashes
        tip.overrideredirect(True)
        tip.attributes("-topmost", True)
        try:
            tip.attributes("-toolwindow", True)  # Win32 only — ignored elsewhere
        except tk.TclError:
            pass
        lbl = tk.Label(tip,
                       text=text,
                       background=self._bg or self._role("surface", "#f0f0f0"),
                       foreground=self._fg or self._role("text", "#000000"),
                       borderwidth=self._bd,
                       relief="solid",
                       wraplength=self._wraplength,
                       justify="left",
                       padx=6, pady=3)
        lbl.pack()

        #?Pointing at the tip keeps it up; leaving it starts the grace period
        # again.  Both the Toplevel and its Label are bound because the Label
        # fills the window, so it is what the pointer actually enters.
        for part in (tip, lbl):
            part.bind("<Enter>", lambda _e: self._cancel_hide(), add="+")
            part.bind("<Leave>", lambda _e: self._schedule_hide(), add="+")

        #?Keep the tip on the desktop.  Bounds come from the VIRTUAL root, not
        # winfo_screenwidth/height: on a multi-monitor setup those report the
        # PRIMARY monitor only, so clamping to them would drag a tip shown on a
        # secondary display back onto the primary one -- worse than the overflow
        # being fixed.  vroot spans every monitor, so this only ever pulls a tip
        # back from genuinely off-desktop.
        try:
            tip.update_idletasks()
            w, h = tip.winfo_reqwidth(), tip.winfo_reqheight()
            #?Anchor names the tip corner that lands on the pointer, so the
            # size has to be known first -- hence positioning here and not
            # before the label exists.
            x = px + self._offset[0] - (w if "e" in self._anchor else 0)
            y = py + self._offset[1] - (h if "s" in self._anchor else 0)
            left, top = self.widget.winfo_vrootx(), self.widget.winfo_vrooty()
            right = left + self.widget.winfo_vrootwidth()
            bottom = top + self.widget.winfo_vrootheight()
            #?Flip to the pointer's other side rather than sliding along the
            # edge, so the cursor never ends up sitting on top of the text.
            if x + w > right:
                x = max(left, px - w - self._offset[0])
            if x < left:
                x = left
            if y + h > bottom:
                y = max(top, py - h - self._offset[1])
            if y < top:
                y = top
            tip.geometry(f"+{x}+{y}")
            tip.deiconify()
        except tk.TclError:
            pass

        self._tip = tip

    def _destroy_tip(self) -> None:
        if self._tip is not None:
            try:
                self._tip.destroy()
            except tk.TclError:
                pass
            self._tip = None
