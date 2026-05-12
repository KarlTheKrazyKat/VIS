"""AutocompleteEntry widget (0.5.0).

A drop-in :class:`ttk.Entry` that filters a candidate list as the user
types and shows the matches in a popup ``Listbox``::

    cities = ["Boston", "Chicago", "Cleveland", "Columbus", "Dallas", ...]
    AutocompleteEntry(parent, values=cities).pack(fill="x")

The candidate list can be a static iterable or a callable returning an
iterable — use the callable form for dynamic lookups (e.g. database
prefix queries).

Keyboard:

- ``Down`` / ``Up`` move the highlight in the popup
- ``Return`` accepts the highlighted entry
- ``Escape`` closes the popup without changing the entry text
- ``Tab`` accepts the first match
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable, Iterable


class AutocompleteEntry(ttk.Entry):
    """``ttk.Entry`` with a filtered dropdown of suggestions."""

    def __init__(self, master, *,
                 values: Iterable[str] | Callable[[str], Iterable[str]] = (),
                 max_results: int = 8,
                 case_sensitive: bool = False,
                 match: str = "prefix",
                 **kwargs):
        """
        Args:
            master:         Parent widget.
            values:         Either an iterable of suggestion strings, or
                            a callable taking the current entry text and
                            returning an iterable.
            max_results:    Cap on the number of suggestions shown.
            case_sensitive: When ``False`` (default), matching ignores
                            case.
            match:          ``"prefix"`` (default) or ``"contains"``.
            **kwargs:       Forwarded to :class:`ttk.Entry`.  If a
                            ``textvariable`` is not supplied one is
                            created and exposed as ``self.var``.
        """
        if "textvariable" not in kwargs:
            kwargs["textvariable"] = tk.StringVar()
        super().__init__(master, **kwargs)
        self.var: tk.StringVar = kwargs["textvariable"]
        self._values_src = values
        self._max_results = max_results
        self._case_sensitive = case_sensitive
        self._match_mode = match if match in ("prefix", "contains") else "prefix"

        self._popup: tk.Toplevel | None = None
        self._listbox: tk.Listbox | None = None
        self._suppress_next_show = False

        self.var.trace_add("write", lambda *_: self._on_text_change())
        self.bind("<Down>",   self._on_down,   add="+")
        self.bind("<Up>",     self._on_up,     add="+")
        self.bind("<Return>", self._on_return, add="+")
        self.bind("<Escape>", self._on_escape, add="+")
        self.bind("<Tab>",    self._on_tab,    add="+")
        self.bind("<FocusOut>", self._on_focus_out, add="+")
        self.bind("<Destroy>",  lambda e: self._hide_popup(), add="+")

    # ── Public API ─────────────────────────────────────────────────────────

    def set_values(self,
                   values: Iterable[str] | Callable[[str], Iterable[str]]
                   ) -> None:
        """Replace the suggestion source."""
        self._values_src = values

    # ── Filtering ──────────────────────────────────────────────────────────

    def _candidates(self, text: str) -> list[str]:
        if callable(self._values_src):
            try:
                raw = list(self._values_src(text))
            except Exception:
                raw = []
        else:
            raw = list(self._values_src)

        if not text:
            return raw[:self._max_results]

        needle = text if self._case_sensitive else text.lower()
        out: list[str] = []
        for v in raw:
            haystack = v if self._case_sensitive else v.lower()
            if self._match_mode == "prefix":
                ok = haystack.startswith(needle)
            else:
                ok = needle in haystack
            if ok:
                out.append(v)
                if len(out) >= self._max_results:
                    break
        return out

    # ── Popup lifecycle ────────────────────────────────────────────────────

    def _on_text_change(self) -> None:
        if self._suppress_next_show:
            self._suppress_next_show = False
            return
        self._refresh_popup()

    def _refresh_popup(self) -> None:
        text = self.var.get()
        matches = self._candidates(text)
        if not matches:
            self._hide_popup()
            return
        self._show_popup(matches)

    def _show_popup(self, matches: list[str]) -> None:
        if self._popup is None:
            self._popup = tk.Toplevel(self)
            self._popup.overrideredirect(True)
            self._popup.attributes("-topmost", True)
            self._listbox = tk.Listbox(
                self._popup,
                height=min(len(matches), self._max_results),
                activestyle="dotbox",
                exportselection=False,
            )
            self._listbox.pack(fill="both", expand=True)
            self._listbox.bind("<ButtonRelease-1>", self._on_click)
        else:
            self._listbox.configure(height=min(len(matches), self._max_results))

        self._listbox.delete(0, "end")
        for m in matches:
            self._listbox.insert("end", m)
        if matches:
            self._listbox.selection_clear(0, "end")
            self._listbox.selection_set(0)
            self._listbox.activate(0)

        # Position just below the entry.
        try:
            x = self.winfo_rootx()
            y = self.winfo_rooty() + self.winfo_height()
            w = self.winfo_width()
        except tk.TclError:
            return
        self._popup.geometry(f"{max(w, 120)}x{self._listbox.winfo_reqheight()}+{x}+{y}")

    def _hide_popup(self) -> None:
        if self._popup is not None:
            try:
                self._popup.destroy()
            except tk.TclError:
                pass
        self._popup = None
        self._listbox = None

    # ── Key handlers ───────────────────────────────────────────────────────

    def _selected_index(self) -> int | None:
        if self._listbox is None:
            return None
        sel = self._listbox.curselection()
        return sel[0] if sel else None

    def _move_selection(self, delta: int) -> None:
        if self._listbox is None:
            return
        n = self._listbox.size()
        if n == 0:
            return
        cur = self._selected_index()
        new = 0 if cur is None else (cur + delta) % n
        self._listbox.selection_clear(0, "end")
        self._listbox.selection_set(new)
        self._listbox.activate(new)
        self._listbox.see(new)

    def _accept(self, idx: int | None = None) -> None:
        if self._listbox is None:
            return
        if idx is None:
            idx = self._selected_index()
        if idx is None:
            return
        value = self._listbox.get(idx)
        self._suppress_next_show = True
        self.var.set(value)
        self.icursor("end")
        self._hide_popup()

    def _on_down(self, _event):
        if self._listbox is None:
            self._refresh_popup()
            return "break"
        self._move_selection(+1)
        return "break"

    def _on_up(self, _event):
        if self._listbox is None:
            return
        self._move_selection(-1)
        return "break"

    def _on_return(self, _event):
        if self._listbox is None:
            return
        self._accept()
        return "break"

    def _on_tab(self, _event):
        if self._listbox is None:
            return
        self._accept(0)
        # Allow normal tab traversal afterwards.
        return None

    def _on_escape(self, _event):
        if self._listbox is None:
            return
        self._hide_popup()
        return "break"

    def _on_click(self, _event):
        self._accept()

    def _on_focus_out(self, _event):
        # Close on focus-out unless focus moved into the popup itself.
        try:
            new_focus = self.focus_get()
        except tk.TclError:
            new_focus = None
        if new_focus is not None and self._listbox is not None and (
                str(new_focus).startswith(str(self._listbox))):
            return
        self._hide_popup()
