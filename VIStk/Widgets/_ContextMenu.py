"""ContextMenu widget (0.5.4).

A thin wrapper around :class:`tkinter.Menu` + ``tk_popup`` so screens get
right-click popup menus without re-rolling the bind/build/popup boilerplate
every time (the pattern ``_TabBar`` hand-codes today).

This is the *native* menu — Tk draws it, so keyboard navigation, hover
submenus, click-outside dismissal and screen-edge clipping all come for
free.  It renders as the classic system menu, not a ttk-themed widget; for
a fully VIStk-styled popup a custom Toplevel would be needed instead.

Usage::

    from VIStk.Widgets import ContextMenu

    # Auto-bind <Button-3> on a widget:
    ContextMenu(my_tree, items=[
        {"label": "Insert step", "command": insert_fn},
        {"label": "Delete step", "command": delete_fn},
        {"separator": True},
        {"label": "Move", "items": [
            {"label": "Up",   "command": up_fn},
            {"label": "Down", "command": down_fn},
        ]},
    ])

    # Dynamic — items rebuilt on every right-click from the event, so the
    # menu can reflect *what* was clicked (e.g. the step under the cursor):
    ContextMenu(canvas, items=lambda e: build_items(step_at(e.y)))

    # Manual trigger — no auto-bind; you own the binding:
    m = ContextMenu(items=[...])
    widget.bind("<Button-3>", m.show)

Item spec (matches the VIStk menu convention used by ``HostMenu``)::

    {"label": str, "command": callable}              # leaf command
    {"label": str, "items": [<item spec>, ...]}      # cascade submenu
    {"separator": True}                              # separator

Optional per-item extras (native menu features):

    "state":       "normal" (default) or "disabled"
    "checkbutton": True with "variable": BooleanVar  # toggle entry
    "accelerator": str                               # right-aligned hint text
"""

from __future__ import annotations

import tkinter as tk
from typing import Callable

# An ``items`` source is either a static list of specs, or a callable that
# receives the triggering event and returns one (for context-sensitive menus).
ItemSpec = dict
ItemSource = "list[ItemSpec] | Callable[[tk.Event | None], list[ItemSpec]]"


class ContextMenu:
    """Right-click popup menu wrapping :class:`tkinter.Menu`."""

    def __init__(self, widget: tk.Widget | None = None,
                 items: ItemSource = None,
                 *, master: tk.Misc | None = None,
                 tearoff: int = 0,
                 font=None,
                 button: str = "<Button-3>"):
        """
        Args:
            widget:  Optional widget to auto-bind the right-click on.  When
                     given, ``button`` is bound on it; when ``None`` you
                     drive the menu yourself via :meth:`show`/:meth:`popup`.
            items:   A list of item-spec dicts, *or* a callable taking the
                     triggering event and returning such a list.  The
                     callable form is re-evaluated on every popup, so the
                     menu can depend on what was clicked.
            master:  Widget the underlying ``Menu`` is parented to.  Defaults
                     to ``widget``, falling back to the event's widget at
                     popup time.  Only needed when no ``widget`` is supplied
                     and you call :meth:`popup` with no event.
            tearoff: ``Menu`` tearoff option.  Default 0 (no tear-off line).
            font:    Optional font applied to the menu and every submenu.
            button:  Event sequence to auto-bind on ``widget``.  Default
                     ``"<Button-3>"`` (right-click).
        """
        self._widget = widget
        self._items = items
        self._master = master or widget
        self._tearoff = tearoff
        self._font = font

        self._owned: list[tk.Menu] = []   # all live Menu objects (root + subs)

        if widget is not None:
            widget.bind(button, self.show, add="+")
            widget.bind("<Destroy>", self._on_destroy, add="+")

    # ── Public API ─────────────────────────────────────────────────────────

    def set_items(self, items: ItemSource) -> None:
        """Replace the item source (list or callable)."""
        self._items = items

    def show(self, event=None):
        """Event handler: pop the menu at the cursor.

        Suitable as a direct ``bind`` callback — returns ``"break"`` so the
        right-click doesn't also fall through to other handlers.
        """
        if event is not None and getattr(event, "x_root", None) is not None:
            x, y = event.x_root, event.y_root
        else:
            ref = self._widget or self._master
            if ref is None:
                return "break"
            x, y = ref.winfo_pointerx(), ref.winfo_pointery()
        self.popup(x, y, event)
        return "break"

    def popup(self, x_root: int, y_root: int, event=None) -> None:
        """Build and display the menu at absolute screen coords ``(x, y)``."""
        items = self._resolve_items(event)
        if not items:
            return
        master = self._master or (event.widget if event is not None else None)
        if master is None:
            raise RuntimeError(
                "ContextMenu.popup needs a master: pass a widget/master to "
                "the constructor or call via a bound event.")
        menu = self._rebuild(items, master)
        try:
            menu.tk_popup(x_root, y_root)
        finally:
            menu.grab_release()

    # ── Internals ──────────────────────────────────────────────────────────

    def _resolve_items(self, event) -> list:
        src = self._items
        if callable(src):
            try:
                src = src(event)
            except Exception:
                src = []
        return list(src or [])

    def _rebuild(self, items: list, master: tk.Misc) -> tk.Menu:
        self._destroy_menus()
        root = tk.Menu(master, tearoff=self._tearoff)
        self._owned = [root]
        self._build(root, items)
        return root

    def _build(self, menu: tk.Menu, items: list) -> None:
        if self._font is not None:
            menu.configure(font=self._font)
        for spec in items:
            if not isinstance(spec, dict):
                continue
            if spec.get("separator"):
                menu.add_separator()
                continue

            label = spec.get("label", "")
            state = spec.get("state", "normal")

            if "items" in spec:
                sub = tk.Menu(menu, tearoff=self._tearoff)
                self._owned.append(sub)
                self._build(sub, spec["items"])
                menu.add_cascade(label=label, menu=sub, state=state)
            elif spec.get("checkbutton"):
                menu.add_checkbutton(
                    label=label, state=state,
                    variable=spec.get("variable"),
                    command=spec.get("command"),
                    accelerator=spec.get("accelerator"))
            else:
                menu.add_command(
                    label=label, state=state,
                    command=spec.get("command"),
                    accelerator=spec.get("accelerator"))

    def _destroy_menus(self) -> None:
        for m in self._owned:
            try:
                m.destroy()
            except tk.TclError:
                pass
        self._owned = []

    def _on_destroy(self, event=None) -> None:
        if event is not None and event.widget is not self._widget:
            return
        self._destroy_menus()
