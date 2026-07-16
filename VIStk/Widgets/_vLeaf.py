"""RoundedLeaf (0.6.3) — corner-tile rounding for the v *leaf* widgets
(:class:`~VIStk.Widgets.vLabel` and :class:`~VIStk.Widgets.vButton`).

A classic Tk ``Label``/``Button`` has a single image slot and draws its own
text/image *on top of* any child — so the lowered-background trick the container
widgets use (:class:`~VIStk.Widgets._vContainer.RoundedContainer`) can't round a
leaf, and painting the rounded fill *into* the image slot (the earlier approach)
stole the slot from the caller's own image and forced ``compound="center"`` —
which made a caller's image + text overlap instead of laying out natively.

``RoundedLeaf`` keeps the widget an ordinary **solid-background** Label/Button —
so its native ``image`` / ``text`` / ``compound`` / ``anchor`` behave *exactly*
like tkinter — and rounds the corners by laying small tiles over them:

1. Four **corner tiles**, each an exact crop of the very same
   :func:`~VIStk.Widgets._vWidget.rounded_pil_image` the containers paint, so the
   corners look identical.  The interior and straight edges are the widget's own
   solid ``bg`` (the fill), which the crops meet seamlessly.
2. When an ``outline`` is set, four thin **edge strips** (crops of the same
   image) carry the outline along the straight edges between the corners.

The tiles/strips are children lifted above the widget's own content; they sit in
the extreme corners/edges, which are empty for normal centred or ``compound``
content (content is inset by ``padx``/``pady``).  A subclass may override
:meth:`_bind_overlay` to forward events from an overlay back to the widget
(``vButton`` forwards clicks and hover so the corners stay clickable).

The mixin is combined **before** ``vWidget`` so its ``_prepare_rounded`` /
``_render_rounded`` win in the MRO::

    class vLabel(RoundedLeaf, vWidget, Label):   ...
    class vButton(RoundedLeaf, vWidget, Button): ...

and relies on ``vWidget`` for ``_v_radius`` / ``_v_outline`` / ``_v_outline_width``
/ ``_v_corner`` / ``_v_last_size`` / ``_fill_color()`` / ``_resolve_color()``.
"""

from __future__ import annotations

from tkinter import Label
import PIL.ImageTk
from VIStk.Widgets._vWidget import rounded_pil_image


class RoundedLeaf:
    """Rounded corners for a leaf widget, drawn as corner tiles over a solid bg,
    leaving the native image slot / ``compound`` free."""

    def _prepare_rounded(self) -> None:
        """Flatten the widget to a clean solid rectangle; the corners are added
        as overlay tiles in :meth:`_render_rounded`.  Native content options
        (``compound``/``image``/``anchor``/``padx``…) are left untouched."""
        self._v_tiles: dict[str, Label] = {}
        self._v_strips: dict[str, Label] = {}
        # Zero only the chrome that would show square corners; do NOT install a
        # placeholder image (leaf sizes to its native content, like tkinter).
        self.configure(bd=0, highlightthickness=0)

    def _render_rounded(self, event=None) -> None:
        """`<Configure>`/repaint handler: (re)crop the rounded corners (and, with
        an outline, the edge strips) at the current size and lay them over the
        widget's corners/edges."""
        w, h = self.winfo_width(), self.winfo_height()
        if w <= 1 or h <= 1 or (w, h) == self._v_last_size:
            return
        self._v_last_size = (w, h)

        r = min(self._v_radius, w // 2, h // 2)
        fill = self._fill_color() or (255, 255, 255)
        corner = self._resolve_color(self._v_corner) or (240, 240, 240)
        outline = self._resolve_color(self._v_outline)
        ow = self._v_outline_width if (self._v_outline and outline) else 0

        full = rounded_pil_image(w, h, r, fill, corner,
                                 outline=outline, outline_width=ow)
        self._place_corner_tiles(full, w, h, r)
        self._place_edge_strips(full, w, h, r, ow)

    # ── Overlay placement ──────────────────────────────────────────────────────

    def _place_corner_tiles(self, full, w: int, h: int, r: int) -> None:
        """Lay the four r×r rounded-corner crops over the widget's corners."""
        for name, (x, y) in (("tl", (0, 0)), ("tr", (w - r, 0)),
                             ("bl", (0, h - r)), ("br", (w - r, h - r))):
            self._set_overlay(self._v_tiles, name,
                              full.crop((x, y, x + r, y + r)), x, y, r, r)

    def _place_edge_strips(self, full, w: int, h: int, r: int, ow: int) -> None:
        """Carry the outline along the straight edges (only when an outline is
        drawn — without one the widget's own solid bg is the straight edge)."""
        wanted = {}
        if ow > 0:
            wanted = {
                "top":    (r, 0, w - r, ow),
                "bottom": (r, h - ow, w - r, h),
                "left":   (0, r, ow, h - r),
                "right":  (w - ow, r, w, h - r),
            }
        # Drop any strips no longer needed (e.g. outline removed at runtime).
        for name in [n for n in self._v_strips if n not in wanted]:
            self._v_strips.pop(name).destroy()
        for name, (x0, y0, x1, y1) in wanted.items():
            if x1 <= x0 or y1 <= y0:
                continue
            self._set_overlay(self._v_strips, name, full.crop((x0, y0, x1, y1)),
                              x0, y0, x1 - x0, y1 - y0)

    def _set_overlay(self, store: dict, name: str, pil_crop,
                     x: int, y: int, w: int, h: int) -> None:
        """Create/reuse an overlay ``Label`` in *store* showing *pil_crop* at
        (*x*, *y*), lifted above the widget's native content."""
        photo = PIL.ImageTk.PhotoImage(pil_crop)
        overlay = store.get(name)
        if overlay is None:
            overlay = store[name] = Label(self, bd=0, highlightthickness=0,
                                          takefocus=0)
            self._bind_overlay(overlay)
        overlay._v_img = photo                 # keep a ref so Tk won't GC it
        overlay.configure(image=photo)
        overlay.place(x=x, y=y, width=w, height=h)
        overlay.lift()

    def _bind_overlay(self, overlay: Label) -> None:
        """Hook: wire events from a freshly-created overlay back to the widget.
        Default does nothing (``vLabel`` needs no forwarding); ``vButton``
        overrides it to keep the corners clickable and hover-aware."""
