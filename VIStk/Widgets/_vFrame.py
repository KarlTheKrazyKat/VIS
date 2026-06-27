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
  frame.

  A Tk child is an opaque rectangle with no per-widget transparency, so a child
  that reaches a rounded corner squares it off — and there is no way to paint
  the rounded corner *back* over the child without also covering the child's
  content.  The only robust fix is to keep content out of the corner region, so
  ``vFrame`` **insets every child** away from the edges by a few pixels,
  regardless of how it is placed (``.Layout.cell``, plain ``place``, ``pack`` or
  ``grid``).  The inset is **invisible** when the child shares the frame's ``bg``
  (the rounded fill reads as continuous to the edge — the inherited default); it
  is ``ceil(radius·(1 − 1/√2))`` ≈ ``0.293·radius``, size-aware as the corner
  clamps on small frames.  Pass ``inset=`` to override it (``0`` disables).

  At ``radius=0`` it is an ordinary ``LayoutFrame`` (no inset, no painting).

Note: corner blending assumes a solid-colour parent (the area outside the
rounded arc is painted with the parent's background so it blends).

Children added at runtime (after the frame has already been sized) are picked up
on the next resize; call :meth:`~VIStk.Widgets._vWidget.vWidget.refresh` to
re-inset them immediately.
"""

from __future__ import annotations

from math import ceil
from typing import TYPE_CHECKING
from tkinter import Label
import PIL.ImageTk
from VIStk.Widgets._LayoutFrame import LayoutFrame
from VIStk.Widgets._vWidget import vWidget, rounded_pil_image

if TYPE_CHECKING:
    try:
        from typing import Unpack
    except ImportError:                       # Python < 3.11
        from typing_extensions import Unpack
    from tkinter import Misc
    from VIStk.Widgets._vtypes import _FrameKw

# r·(1 − 1/√2): perpendicular inset that lands a content corner on the corner arc
# (the largest axis-aligned rectangle that fits inside the rounded rectangle).
_INSET_FACTOR = 1 - 2 ** -0.5


def _parse_pad(val) -> tuple[int, int]:
    """Normalise a pack/grid ``padx``/``pady`` value to ``(leading, trailing)``.

    Tk reports padding as an int, a 2-tuple, or a space-separated string; this
    collapses all three to a plain ``(int, int)`` so the inset can be layered on
    top of the caller's own padding without losing it."""
    if val is None or val == "":
        return (0, 0)
    if isinstance(val, int):
        return (val, val)
    if isinstance(val, (tuple, list)):
        parts = [int(v) for v in val]
    else:
        parts = [int(p) for p in str(val).split()]
    if not parts:
        return (0, 0)
    if len(parts) == 1:
        return (parts[0], parts[0])
    return (parts[0], parts[1])


class vFrame(vWidget, LayoutFrame):
    """A ``LayoutFrame`` that inherits ``bg`` and can be rounded."""

    _INHERIT = ("background",)

    def __init__(self, master: Misc | None = None, *,
                 radius: int = 0, outline: str | None = None,
                 outline_width: int = 1, corner_bg: str | None = None,
                 inset: int | None = None, **kwargs: Unpack[_FrameKw]):
        """
        Args:
            master:        Parent widget.
            radius:        Corner radius in px; ``0`` (default) → plain
                           ``LayoutFrame``.
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
        super().__init__(master, radius=radius, outline=outline,
                         outline_width=outline_width, corner_bg=corner_bg,
                         **kwargs)
        self._v_inset = inset
        if self._v_radius > 0:
            self.Layout.margin = self._inset_for(self._v_radius)

    def _inset_for(self, radius: int) -> int:
        """Content inset that keeps content inside the corner arc — the largest
        rectangle that fits: ``ceil(r·(1 − 1/√2))``.

        The ideal is sub-pixel (≈ 3.51 px at r=12) but a Tk child is placed on a
        *whole* pixel, so we round **up** — flooring or round-to-nearest can land
        a child a fraction of a pixel *outside* the arc, squaring off the corner.
        Ceiling guarantees the child stays inside the arc; the extra ≤1 px is
        invisible when the child shares the fill."""
        if self._v_inset is not None:
            return self._v_inset
        return ceil(radius * _INSET_FACTOR)

    # ── Rounded overrides ────────────────────────────────────────────────────
    #
    # The rounded fill + outline lives on a single lowered Label image; every
    # child is inset off the edges so its square corners never reach (and square
    # off) the rounded corner.  There is no opaque overlay floated over content.

    def _prepare_rounded(self) -> None:
        fill = self.cget("background")
        self._v_bg_label = Label(self, bd=0, highlightthickness=0, bg=fill,
                                 takefocus=0)
        self._v_bg_label.place(x=0, y=0, relwidth=1, relheight=1)
        self._v_bg_label.lower()

    def _render_rounded(self, event=None) -> None:
        w, h = self.winfo_width(), self.winfo_height()
        if w <= 1 or h <= 1 or (w, h) == self._v_last_size:
            return
        self._v_last_size = (w, h)

        fill = self._fill_color() or (255, 255, 255)
        corner = self._resolve_color(self._v_corner) or (240, 240, 240)
        outline = self._resolve_color(self._v_outline)
        ow = self._v_outline_width if (self._v_outline and outline) else 0

        pil = rounded_pil_image(w, h, self._v_radius, fill, corner,
                                outline=outline, outline_width=ow)
        self._v_bg_image = PIL.ImageTk.PhotoImage(pil)
        self._v_bg_label.configure(image=self._v_bg_image)

        # Keep the inset size-aware: on a small frame the radius (and therefore
        # the inset that keeps content off it) clamps to the short side.
        r = min(self._v_radius, w // 2, h // 2)
        self.Layout.margin = self._inset_for(r)

        # Re-inset once children have settled at the new size (catches both a
        # margin change and any children added since the last render).
        self.after_idle(self._reinset_children)

    # ── Child insetting (all geometry managers) ───────────────────────────────

    def _reinset_children(self) -> None:
        """Inset every child off the frame edges by the current `.Layout.margin`,
        whichever geometry manager placed it.  The inset is layered on top of the
        child's own geometry so the corner stays clear of square child corners;
        the lowered background label is skipped (it must fill the frame)."""
        m = self.Layout.margin
        for child in self.winfo_children():
            if child is getattr(self, "_v_bg_label", None):
                continue
            try:
                mgr = child.winfo_manager()
                if mgr == "place":
                    self._inset_placed(child, m)
                elif mgr == "pack":
                    self._inset_packed(child, m)
                elif mgr == "grid":
                    self._inset_gridded(child, m)
            except Exception:
                continue

    def _inset_placed(self, child, m: int) -> None:
        """Inset a relatively-``place``-d child (relx/rely/relwidth/relheight).

        The relative geometry is the caller's and is preserved; only the fixed
        pixel offset is recomputed from *m*, so re-running never accumulates.
        Absolutely-placed children (no relwidth) are left untouched — their
        pixel coordinates are the caller's exact intent."""
        info = child.place_info()
        if not info or not info.get("relwidth"):
            return
        try:
            relx, rely = float(info["relx"]), float(info["rely"])
            relw, relh = float(info["relwidth"]), float(info["relheight"])
        except (KeyError, TypeError, ValueError):
            return
        child.place(relx=relx, rely=rely, relwidth=relw, relheight=relh,
                    x=round(m * (1 - 2 * relx)), y=round(m * (1 - 2 * rely)),
                    width=round(-2 * m * relw), height=round(-2 * m * relh))

    def _inset_packed(self, child, m: int) -> None:
        """Inset a ``pack``-ed child by adding *m* to its padding (caller padding
        preserved via a one-time captured base)."""
        base = getattr(child, "_v_pad_base", None)
        if base is None:
            pi = child.pack_info()
            base = (_parse_pad(pi.get("padx")), _parse_pad(pi.get("pady")))
            child._v_pad_base = base
        (px0, px1), (py0, py1) = base
        child.pack_configure(padx=(px0 + m, px1 + m), pady=(py0 + m, py1 + m))

    def _inset_gridded(self, child, m: int) -> None:
        """Inset a ``grid``-ded child by adding *m* to its padding (caller padding
        preserved via a one-time captured base)."""
        base = getattr(child, "_v_pad_base", None)
        if base is None:
            gi = child.grid_info()
            base = (_parse_pad(gi.get("padx")), _parse_pad(gi.get("pady")))
            child._v_pad_base = base
        (px0, px1), (py0, py1) = base
        child.grid_configure(padx=(px0 + m, px1 + m), pady=(py0 + m, py1 + m))
