"""CollapsibleFrame widget (0.5.0).

A frame with a header button that toggles the visibility of its content
area::

    cf = CollapsibleFrame(parent, text="Advanced options", expanded=False)
    cf.pack(fill="x", padx=4, pady=4)

    # Pack child widgets into ``cf.body`` (NOT directly into ``cf``):
    ttk.Checkbutton(cf.body, text="Verbose").pack(anchor="w")
    ttk.Entry(cf.body).pack(fill="x")

The frame remembers its expanded state in a ``BooleanVar`` (exposed as
``cf.expanded_var``) so callers can bind it to settings or share it
across frames.

Geometry: when collapsed only the header is visible; when expanded the
body is packed below.  Layout is ``pack``-based so the frame plays
nicely with both ``pack`` and ``grid`` parents.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable


class CollapsibleFrame(ttk.Frame):
    """A frame whose body can be collapsed under a header button."""

    _ARROW_EXPANDED = "\u25BC"   # ▼
    _ARROW_COLLAPSED = "\u25B6"  # ▶

    def __init__(self, master, *, text: str = "",
                 expanded: bool = True,
                 on_toggle: Callable[[bool], None] | None = None,
                 **kwargs):
        """
        Args:
            master:    Parent widget.
            text:      Header label text.
            expanded:  Initial state.  Default ``True``.
            on_toggle: Optional callback invoked with the new expanded
                       state whenever the user toggles the frame.
            **kwargs:  Forwarded to :class:`ttk.Frame`.
        """
        super().__init__(master, **kwargs)
        self._on_toggle = on_toggle

        self.expanded_var = tk.BooleanVar(value=bool(expanded))
        """``BooleanVar`` mirroring the current expanded state.  Bind
        externally to share state across instances or persist it."""

        self._header = ttk.Frame(self)
        self._header.pack(fill="x")

        self._toggle_btn = ttk.Button(
            self._header,
            text=self._compose_label(text),
            style="Toolbutton",
            command=self.toggle,
        )
        self._toggle_btn.pack(fill="x")

        self.body = ttk.Frame(self)
        """The content area.  Pack or grid your widgets into this."""

        self._text = text

        if self.expanded_var.get():
            self.body.pack(fill="both", expand=True)

    # ── Public API ─────────────────────────────────────────────────────────

    def toggle(self) -> None:
        """Flip between expanded and collapsed."""
        self.set_expanded(not self.expanded_var.get())

    def expand(self) -> None:
        """Show the body."""
        self.set_expanded(True)

    def collapse(self) -> None:
        """Hide the body."""
        self.set_expanded(False)

    def set_expanded(self, value: bool) -> None:
        """Set state explicitly.  No-ops if already in the requested state."""
        value = bool(value)
        if self.expanded_var.get() == value and (
                value == bool(self.body.winfo_ismapped())):
            return
        self.expanded_var.set(value)
        if value:
            self.body.pack(fill="both", expand=True)
        else:
            self.body.pack_forget()
        self._toggle_btn.configure(text=self._compose_label(self._text))
        if self._on_toggle is not None:
            try:
                self._on_toggle(value)
            except Exception:
                pass

    def set_text(self, text: str) -> None:
        """Update the header label."""
        self._text = text
        self._toggle_btn.configure(text=self._compose_label(text))

    # ── Internals ──────────────────────────────────────────────────────────

    def _compose_label(self, text: str) -> str:
        arrow = (self._ARROW_EXPANDED if self.expanded_var.get()
                 else self._ARROW_COLLAPSED)
        return f"{arrow}  {text}" if text else arrow
