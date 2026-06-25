"""vLabel (0.6.2) — a classic ``tk.Label`` that inherits parent traits and
optionally renders rounded corners.

A drop-in replacement for :class:`tkinter.Label` (all native options and
methods work unchanged) that adds two conveniences::

    pane = Frame(root, bg="white")
    vLabel(pane, text="Hello").pack()          # bg/fg/font inherited → white
    vLabel(pane, text="Pill", bg="#2f78d3", fg="white",
           radius=11).pack()                   # rounded "pill"

* **Inheritance** — ``background``, ``foreground`` and ``font`` default to the
  parent's values when omitted, so a label dropped into a white frame no
  longer shows the default grey background.  Anything passed explicitly wins.
* **Rounded corners** — opt in with ``radius`` > 0; the text is drawn centred
  over an anti-aliased rounded fill (see :class:`vWidget`).  With ``radius=0``
  (the default) it is an ordinary ``Label``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from tkinter import Label
from VIStk.Widgets._vWidget import vWidget

if TYPE_CHECKING:
    try:
        from typing import Unpack
    except ImportError:                       # Python < 3.11
        from typing_extensions import Unpack
    from tkinter import Misc
    from VIStk.Widgets._vtypes import _LabelKw


class vLabel(vWidget, Label):
    """A ``Label`` that inherits ``bg``/``fg``/``font`` and can be rounded."""

    _INHERIT = ("background", "foreground", "font")

    def __init__(self, master: Misc | None = None, *,
                 radius: int = 0, outline: str | None = None,
                 outline_width: int = 1, corner_bg: str | None = None,
                 **kwargs: Unpack[_LabelKw]):
        """
        Args:
            master:        Parent widget.
            radius:        Corner radius in px; ``0`` (default) → plain Label.
            outline:       Optional border colour for the rounded fill.
            outline_width: Border width in px (default ``1``; needs *outline*).
            corner_bg:     Corner blend colour (defaults to the parent's bg).
            **kwargs:      Any native :class:`tkinter.Label` option (see below).
                           ``bg`` / ``fg`` / ``font`` are inherited from
                           *master* when omitted.
        """
        super().__init__(master, radius=radius, outline=outline,
                         outline_width=outline_width, corner_bg=corner_bg,
                         **kwargs)
