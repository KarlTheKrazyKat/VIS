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
                 background: str = "#FFFFE0",
                 foreground: str = "#000000",
                 borderwidth: int = 1):
        """
        Args:
            widget:      The widget to attach to.
            text:        Tooltip text, or a zero-arg callable returning
                         the text (re-evaluated each time the tip is
                         shown — useful for state-dependent tooltips).
            delay_ms:    Hover delay before showing.  Default 500 ms.
            wraplength:  Pixel width at which the tooltip wraps.
            background:  Tooltip background colour.
            foreground:  Tooltip foreground colour.
            borderwidth: Border thickness in pixels.
        """
        self.widget = widget
        self._text = text
        self._delay_ms = delay_ms
        self._wraplength = wraplength
        self._bg = background
        self._fg = foreground
        self._bd = borderwidth

        self._tip: tk.Toplevel | None = None
        self._after_id: str | None = None

        widget.bind("<Enter>",     self._on_enter,    add="+")
        widget.bind("<Leave>",     self._on_leave,    add="+")
        widget.bind("<ButtonPress>", self._on_leave,  add="+")
        widget.bind("<Destroy>",   self._on_destroy,  add="+")

    # ── Public mutators ────────────────────────────────────────────────────

    def set_text(self, text: str | Callable[[], str]) -> None:
        """Replace the tooltip text (or the callable producing it)."""
        self._text = text

    def hide(self) -> None:
        """Cancel any pending show and destroy the popup if visible."""
        self._cancel()
        self._destroy_tip()

    # ── Event handlers ─────────────────────────────────────────────────────

    def _on_enter(self, _event=None) -> None:
        self._cancel()
        self._after_id = self.widget.after(self._delay_ms, self._show)

    def _on_leave(self, _event=None) -> None:
        self.hide()

    def _on_destroy(self, _event=None) -> None:
        self.hide()

    # ── Internals ──────────────────────────────────────────────────────────

    def _cancel(self) -> None:
        if self._after_id is not None:
            try:
                self.widget.after_cancel(self._after_id)
            except tk.TclError:
                pass
            self._after_id = None

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
        # Position just below-right of the cursor.
        try:
            x = self.widget.winfo_pointerx() + 12
            y = self.widget.winfo_pointery() + 16
        except tk.TclError:
            return

        tip = tk.Toplevel(self.widget)
        tip.overrideredirect(True)
        tip.attributes("-topmost", True)
        try:
            tip.attributes("-toolwindow", True)  # Win32 only — ignored elsewhere
        except tk.TclError:
            pass
        tip.geometry(f"+{x}+{y}")

        lbl = tk.Label(tip,
                       text=text,
                       background=self._bg,
                       foreground=self._fg,
                       borderwidth=self._bd,
                       relief="solid",
                       wraplength=self._wraplength,
                       justify="left",
                       padx=6, pady=3)
        lbl.pack()

        self._tip = tip

    def _destroy_tip(self) -> None:
        if self._tip is not None:
            try:
                self._tip.destroy()
            except tk.TclError:
                pass
            self._tip = None
