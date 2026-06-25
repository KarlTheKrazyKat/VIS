"""vButton (0.6.2) — a classic ``tk.Button`` that inherits parent traits and
optionally renders rounded corners.

A drop-in replacement for :class:`tkinter.Button` (all native options and
methods, including ``command``/``invoke``, work unchanged) that adds the same
two conveniences as :class:`~VIStk.Widgets.vLabel`::

    bar = Frame(root, bg="white")
    vButton(bar, text="Save", command=save).pack()       # bg/fg/font inherited
    vButton(bar, text="Quote", command=quote, radius=8,  # rounded "chip"
            bg="#eef1f6", fg="#2f78d3",
            active_fill="#dbe6f6").pack()                 # hover fill

* **Inheritance** — ``background``/``foreground``/``font`` default to the
  parent's values when omitted; explicit options win.
* **Rounded corners** — opt in with ``radius`` > 0; the label is drawn centred
  over an anti-aliased rounded fill, the relief is flattened, and an optional
  ``active_fill`` repaints the fill on hover (mirrors the chip-button pattern
  the PYWOM screens hand-roll today).  At ``radius=0`` it is an ordinary
  ``Button``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from tkinter import Button
from VIStk.Widgets._vWidget import vWidget

if TYPE_CHECKING:
    try:
        from typing import Unpack
    except ImportError:                       # Python < 3.11
        from typing_extensions import Unpack
    from tkinter import Misc
    from VIStk.Widgets._vtypes import _ButtonKw


class vButton(vWidget, Button):
    """A ``Button`` that inherits ``bg``/``fg``/``font`` and can be rounded."""

    _INHERIT = ("background", "foreground", "font")
    # A state change also re-greys the rounded fill (see _fill_color).
    _REPAINT_OPTS = ("background", "bg", "state")

    def __init__(self, master: Misc | None = None, *,
                 radius: int = 0, outline: str | None = None,
                 outline_width: int = 1, corner_bg: str | None = None,
                 active_fill: str | None = None,
                 disabled_fill: str = "#e9ecef", **kwargs: Unpack[_ButtonKw]):
        """
        Args:
            master:        Parent widget.
            radius:        Corner radius in px; ``0`` (default) → plain Button.
            outline:       Optional border colour for the rounded fill.
            outline_width: Border width in px (default ``1``; needs *outline*).
            corner_bg:     Corner blend colour (defaults to the parent's bg).
            active_fill:   Optional hover fill colour (rounded mode only).
            disabled_fill: Fill painted when ``state="disabled"`` (rounded mode);
                           pair with ``configure(state=...)`` to grey the button.
            **kwargs:      Any native :class:`tkinter.Button` option (see below).
                           ``bg`` / ``fg`` / ``font`` are inherited from
                           *master* when omitted.
        """
        # Hover / disabled state — set before super().__init__ so _fill_color
        # (which may run on the first <Configure>) sees them.
        self._v_active_fill = active_fill
        self._v_disabled_fill = disabled_fill
        self._v_hover = False
        super().__init__(master, radius=radius, outline=outline,
                         outline_width=outline_width, corner_bg=corner_bg,
                         **kwargs)
        if self._v_radius > 0 and active_fill:
            self.bind("<Enter>", self._on_enter, add="+")
            self.bind("<Leave>", self._on_leave, add="+")

    # ── Rounded overrides ──────────────────────────────────────────────────────

    def _prepare_rounded(self) -> None:
        # Flatten the relief so the painted fill is the only visible chrome
        # (no sunken edge on press, no raised border at rest or on hover) and
        # show a hand cursor on the clickable area.
        super()._prepare_rounded()
        self.configure(relief="flat", overrelief="flat", cursor="hand2")

    def _fill_color(self):
        # disabled wins over hover wins over the base background.
        if str(self.cget("state")) == "disabled":
            c = self._resolve_color(self._v_disabled_fill)
            if c:
                return c
        if self._v_hover and self._v_active_fill:
            c = self._resolve_color(self._v_active_fill)
            if c:
                return c
        return super()._fill_color()

    def configure(self, cnf=None, **kw):
        result = super().configure(cnf, **kw)   # vWidget handles fill repaint
        if getattr(self, "_v_radius", 0) > 0:
            keys = set(kw) | (set(cnf) if isinstance(cnf, dict) else set())
            if "state" in keys:
                disabled = str(self.cget("state")) == "disabled"
                super().configure(cursor="arrow" if disabled else "hand2")
        return result

    config = configure

    def _on_enter(self, event=None) -> None:
        self._v_hover = True
        self._v_last_size = (0, 0)   # force a repaint with the active fill
        self._render_rounded()

    def _on_leave(self, event=None) -> None:
        self._v_hover = False
        self._v_last_size = (0, 0)
        self._render_rounded()
