"""vFrame (0.6.2) — a :class:`~VIStk.Widgets.LayoutFrame` that inherits its
parent's background and optionally renders rounded corners.

``vFrame`` keeps everything ``LayoutFrame`` gives you (the attached
``.Layout`` helper) and adds the v-widget conveniences::

    card = vFrame(root, bg="white", radius=14)   # white rounded card on a
    card.place(relx=.1, rely=.1, relwidth=.8, relheight=.8)  # grey parent
    card.Layout.colSize([1.0]); card.Layout.rowSize([1.0])
    vLabel(card, text="Inside").place(card.Layout.cell(1, 1))

* **Inheritance** — only ``background`` (Frames have no fg/font); it defaults
  to the parent's background when omitted, so a plain container blends in.
* **Rounded corners** — opt in with ``radius`` > 0.  The frame's ``bg`` is the
  **fill**; a single anti-aliased rounded rectangle (fill + optional
  ``outline``) is drawn onto a *lowered* background ``Label`` that fills the
  frame, and every child is inset off the corners so its square corners stay
  inside the rounded ones (see :class:`~VIStk.Widgets._vContainer.RoundedContainer`
  for the full two-layer mechanism, shared with :class:`vLabelFrame`).

  At ``radius=0`` it is an ordinary ``LayoutFrame`` (no inset, no painting).

Note: corner blending assumes a solid-colour parent (the area outside the
rounded arc is painted with the parent's background so it blends).

Children added at runtime (after the frame has already been sized) are picked up
on the next resize; call :meth:`~VIStk.Widgets._vWidget.vWidget.refresh` to
re-inset them immediately.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from VIStk.Widgets._LayoutFrame import LayoutFrame
from VIStk.Widgets._vWidget import vWidget
from VIStk.Widgets._vContainer import RoundedContainer

if TYPE_CHECKING:
    try:
        from typing import Unpack
    except ImportError:                       # Python < 3.11
        from typing_extensions import Unpack
    from tkinter import Misc
    from VIStk.Widgets._vtypes import _FrameKw


class vFrame(RoundedContainer, vWidget, LayoutFrame):
    """A ``LayoutFrame`` that inherits ``bg`` and can be rounded."""

    _INHERIT = ("background",)

    def __init__(self, master: Misc | None = None, *,
                 radius: int = 0, radius_style: str = "pixels",
                 outline: str | None = None,
                 outline_width: int = 1, corner_bg: str | None = None,
                 inset: int | None = None, **kwargs: Unpack[_FrameKw]):
        """
        Args:
            master:        Parent widget.
            radius:        Corner radius; ``0`` (default) → plain
                           ``LayoutFrame``.  Read as pixels, or as a percentage
                           per *radius_style*.
            radius_style:  ``"pixels"`` (default) → *radius* is a pixel radius;
                           ``"percent"`` → it is a percentage of the maximum
                           round (half the short side), so ``radius=100`` is a
                           full pill/circle at any size.  Re-resolved on every
                           resize (the content inset follows it).
            outline:       Optional border colour for the rounded fill.
            outline_width: Border width in px (default ``1``; needs *outline*).
            corner_bg:     Corner blend colour (defaults to the parent's bg).
            inset:         Content inset (`.Layout.margin`) in px applied to every
                           child, however it is placed.  ``None`` (default)
                           auto-computes the value that keeps content clear of the
                           rounded corner — the largest rectangle that fits —
                           ``ceil(radius·(1 − 1/√2))``.  Invisible when the child
                           shares the frame's fill.  Pass a larger value to pull
                           content further in, or ``0`` for none.
            **kwargs:      Any native :class:`tkinter.Frame` option (see below).
                           ``bg`` is inherited from *master* when omitted, and
                           is used as the rounded fill colour.
        """
        super().__init__(master, radius=radius, radius_style=radius_style,
                         outline=outline,
                         outline_width=outline_width, corner_bg=corner_bg,
                         **kwargs)
        self._setup_container(inset)
