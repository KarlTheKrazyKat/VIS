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
* **Rounded corners** — opt in with ``radius`` > 0.  A ``Frame`` has no
  ``image`` option, so the rounded fill is painted onto a lowered background
  ``Label`` that fills the frame; child widgets placed via ``.Layout`` /
  ``place`` stack above it (the same idea as PYWOM's ``make_round_box``).  The
  frame's ``bg`` is the **fill**; the corners blend with the parent's
  background.  At ``radius=0`` it is an ordinary ``LayoutFrame``.

Note: the lowered background label receives pointer events over empty (non-
child) areas, and corner blending assumes a solid-colour parent.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from tkinter import Label
from VIStk.Widgets._LayoutFrame import LayoutFrame
from VIStk.Widgets._vWidget import vWidget

if TYPE_CHECKING:
    try:
        from typing import Unpack
    except ImportError:                       # Python < 3.11
        from typing_extensions import Unpack
    from tkinter import Misc
    from VIStk.Widgets._vtypes import _FrameKw


class vFrame(vWidget, LayoutFrame):
    """A ``LayoutFrame`` that inherits ``bg`` and can be rounded."""

    _INHERIT = ("background",)

    def __init__(self, master: Misc | None = None, *,
                 radius: int = 0, outline: str | None = None,
                 outline_width: int = 1, corner_bg: str | None = None,
                 **kwargs: Unpack[_FrameKw]):
        """
        Args:
            master:        Parent widget.
            radius:        Corner radius in px; ``0`` (default) → plain
                           ``LayoutFrame``.
            outline:       Optional border colour for the rounded fill.
            outline_width: Border width in px (default ``1``; needs *outline*).
            corner_bg:     Corner blend colour (defaults to the parent's bg).
            **kwargs:      Any native :class:`tkinter.Frame` option (see below).
                           ``bg`` is inherited from *master* when omitted, and
                           is used as the rounded fill colour.
        """
        super().__init__(master, radius=radius, outline=outline,
                         outline_width=outline_width, corner_bg=corner_bg,
                         **kwargs)

    # ── Rounded overrides (paint a lowered background label, not self) ──────────

    def _prepare_rounded(self) -> None:
        # Frame has no image option, so the rounded fill lives on a background
        # Label that fills the frame and sits below every child.  Seed its bg
        # with the fill colour so there's no grey flash before the first paint.
        fill = self.cget("background")
        self._v_bg_label = Label(self, bd=0, highlightthickness=0, bg=fill)
        self._v_bg_label.place(x=0, y=0, relwidth=1, relheight=1)
        self._v_bg_label.lower()

    def _paint(self, image) -> None:
        self._v_bg_image = image
        self._v_bg_label.configure(image=image)
