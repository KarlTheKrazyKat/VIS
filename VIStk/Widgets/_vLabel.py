"""vLabel (0.6.3) — a classic ``tk.Label`` that inherits parent traits and
optionally renders rounded corners.

A drop-in replacement for :class:`tkinter.Label` (all native options and
methods work unchanged) that adds two conveniences::

    pane = Frame(root, bg="white")
    vLabel(pane, text="Hello").pack()          # bg/fg/font inherited → white
    vLabel(pane, text="Pill", bg="#2f78d3", fg="white",
           radius=11).pack()                   # rounded "pill"
    vLabel(pane, text="Item", image=icon,      # icon + text laid out natively
           compound="left", radius=11).pack()

* **Inheritance** — ``background``, ``foreground`` and ``font`` default to the
  parent's values when omitted, so a label dropped into a white frame no
  longer shows the default grey background.  Anything passed explicitly wins.
* **Rounded corners** — opt in with ``radius`` > 0 (see
  :class:`~VIStk.Widgets._vLeaf.RoundedLeaf`).  A text-only label paints the
  rounded fill into its image slot and draws the text over it, so the text is
  never covered at *any* radius — including a true circle.  Passing your own
  ``image=`` switches to corner-tile rounding, which leaves the native image
  slot free so ``image`` / ``compound`` / ``anchor`` behave exactly as on a
  native ``Label`` (keep the radius modest in that mode — the tiles are opaque).
  With ``radius=0`` (the default) it is an ordinary ``Label``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from tkinter import Label
from VIStk.Widgets._vWidget import vWidget
from VIStk.Widgets._vLeaf import RoundedLeaf

if TYPE_CHECKING:
    try:
        from typing import Unpack
    except ImportError:                       # Python < 3.11
        from typing_extensions import Unpack
    from tkinter import Misc
    from VIStk.Widgets._vtypes import _LabelKw


class vLabel(RoundedLeaf, vWidget, Label):
    """A ``Label`` that inherits ``bg``/``fg``/``font`` and can be rounded.

    Rounded mode leaves the Label an ordinary solid-background Label and rounds
    the corners with overlay tiles (:class:`~VIStk.Widgets._vLeaf.RoundedLeaf`),
    so ``image`` / ``text`` / ``compound`` / ``anchor`` all behave exactly as on
    a native ``tkinter.Label`` — a caller image and text lay out via ``compound``
    with no overlap.
    """

    _INHERIT = ("background", "foreground", "font")

    def __init__(self, master: Misc | None = None, *,
                 radius: int = 0, radius_style: str = "pixels",
                 outline: str | None = None,
                 outline_width: int = 1, corner_bg: str | None = None,
                 **kwargs: Unpack[_LabelKw]):
        """
        Args:
            master:        Parent widget.
            radius:        Corner radius; ``0`` (default) → plain Label.  Read as
                           pixels, or as a percentage per *radius_style*.
            radius_style:  ``"pixels"`` (default) → *radius* is a pixel radius;
                           ``"percent"`` → it is a percentage of the maximum
                           round (half the short side), so ``radius=100`` is a
                           full pill/circle at any size.  Re-resolved on every
                           resize.
            outline:       Optional border colour for the rounded fill.
            outline_width: Border width in px (default ``1``; needs *outline*).
            corner_bg:     Corner blend colour (defaults to the parent's bg).
            **kwargs:      Any native :class:`tkinter.Label` option (see below).
                           ``bg`` / ``fg`` / ``font`` are inherited from
                           *master* when omitted.
        """
        super().__init__(master, radius=radius, radius_style=radius_style,
                         outline=outline,
                         outline_width=outline_width, corner_bg=corner_bg,
                         **kwargs)
