"""Standard confirmation dialogs (0.5.0).

Helpers that keep screens from re-implementing the ``tkinter.messagebox``
dance every time they need to veto ``on_quit`` or confirm a destructive
action.  Both dialogs are modal, centred on their parent via
:meth:`WindowGeometry.center_on` (so they never flash at the OS default
position), and return a plain ``bool``.

Typical usage inside ``on_quit``::

    from VIStk.Widgets import confirm_discard

    def on_quit() -> bool:
        if not _dirty:
            return True
        result = confirm_discard(name="Work Order #12345")
        if result == "cancel":
            return False
        if result == "save":
            _save()
        return True
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Literal

from VIStk.Objects._WindowGeometry import WindowGeometry


def _get_parent():
    """Return the current default root, falling back to ``None``."""
    try:
        return tk._default_root
    except Exception:
        return None


class _ModalDialog(tk.Toplevel):
    """Shared Toplevel used by :func:`confirm` and :func:`confirm_discard`.

    Centres on the parent and grabs input until a button is pressed or
    the window is closed.
    """

    def __init__(self, parent, title: str, message: str,
                 buttons: list[tuple[str, object]], *,
                 default_value=None, escape_value=None):
        super().__init__(parent)
        # Hide immediately so only the centred, fully-built window is
        # ever shown (no flicker at OS default position).
        self.withdraw()
        self.title(title)
        self.resizable(False, False)

        self._result = default_value if default_value is not None else escape_value

        body = ttk.Frame(self, padding=(16, 14, 16, 10))
        body.pack(fill="both", expand=True)

        ttk.Label(body, text=message, wraplength=360, justify="left").pack(
            fill="x", pady=(0, 14))

        btn_row = ttk.Frame(body)
        btn_row.pack(fill="x")
        btn_row.columnconfigure(0, weight=1)

        spacer = ttk.Frame(btn_row)
        spacer.grid(row=0, column=0, sticky="ew")

        for i, (label, value) in enumerate(buttons, start=1):
            b = ttk.Button(btn_row, text=label,
                           command=lambda v=value: self._finish(v))
            b.grid(row=0, column=i, padx=(6, 0))
            if default_value is not None and value == default_value:
                b.focus_set()
                self.bind("<Return>", lambda e, v=value: self._finish(v))

        if escape_value is not None:
            self.bind("<Escape>", lambda e: self._finish(escape_value))
        self.protocol("WM_DELETE_WINDOW",
                      lambda: self._finish(escape_value))

        # Geometry + modality.
        WindowGeometry(self)
        if parent is not None and int(parent.winfo_viewable()):
            self.WindowGeometry.center_on(parent)
        else:
            self.WindowGeometry.getGeometry(True)
            self.WindowGeometry.setGeometry(
                width=self.winfo_width(),
                height=self.winfo_height(),
                align="center",
                size_style="screen_relative")
            self.deiconify()

        self.transient(parent) if parent is not None else None
        self.grab_set()
        self.wait_window()

    def _finish(self, value):
        self._result = value
        try:
            self.grab_release()
        except tk.TclError:
            pass
        self.destroy()


def confirm(parent=None, *, title: str, message: str,
            yes: str = "Yes", no: str = "No") -> bool:
    """Generic two-button Yes/No confirmation dialog.

    Returns ``True`` when the user clicks *yes*, ``False`` when they
    click *no*, press Escape, or close the window.

    Args:
        parent:  Window to centre the dialog on.  ``None`` uses the
            current default root; if there isn't one the dialog centres
            on the screen.
        title:   Window title.
        message: Body text.  Wraps at ~360 px.
        yes:     Label for the affirmative button.  Default ``"Yes"``.
        no:      Label for the negative button.  Default ``"No"``.
    """
    parent = parent if parent is not None else _get_parent()
    dlg = _ModalDialog(
        parent, title=title, message=message,
        buttons=[(no, False), (yes, True)],
        default_value=True, escape_value=False)
    return bool(dlg._result)


def confirm_discard(parent=None, *, title: str | None = None,
                    message: str | None = None,
                    name: str | None = None
                    ) -> Literal["save", "discard", "cancel"]:
    """Three-button *Save / Discard / Cancel* dialog.

    Drop-in helper for ``on_quit``::

        def on_quit() -> bool:
            if not _dirty:
                return True
            choice = confirm_discard(name="Work Order #12345")
            if choice == "cancel":
                return False
            if choice == "save":
                _save()
            return True

    Args:
        parent:  Window to centre the dialog on.  ``None`` uses the
            current default root.
        title:   Window title.  Defaults to ``"Unsaved changes"``.
        message: Body text.  When ``None`` a default is built from *name*.
        name:    Optional item identifier (e.g. ``"Work Order #12345"``)
            spliced into the default message when *message* is ``None``.

    Returns:
        One of ``"save"``, ``"discard"``, or ``"cancel"``.  Escape or
        closing the window both return ``"cancel"``.
    """
    parent = parent if parent is not None else _get_parent()
    if title is None:
        title = "Unsaved changes"
    if message is None:
        target = name or "this item"
        message = (f"Save changes to {target} before closing?\n\n"
                   f"Choose Discard to close without saving, or Cancel "
                   f"to keep it open.")
    dlg = _ModalDialog(
        parent, title=title, message=message,
        buttons=[("Cancel", "cancel"),
                 ("Discard", "discard"),
                 ("Save", "save")],
        default_value="save",
        escape_value="cancel")
    return dlg._result
