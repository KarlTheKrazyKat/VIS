"""RoundedLeaf (0.6.3) — rounded-corner machinery for the v *leaf* widgets
(:class:`~VIStk.Widgets.vLabel` and :class:`~VIStk.Widgets.vButton`).

A classic Tk ``Label``/``Button`` has **one** image slot, and that single slot is
the only per-widget surface we can paint on — which forces a choice, because the
rounded fill and the caller's own ``image=`` both want it:

**Fill mode** (no caller ``image=``) — the rounded fill is painted *into* the
image slot with ``compound="center"``.  The widget's text is its own content and
is drawn **over** that fill, so it is never covered: this works at *any* radius,
including a true circle (``radius`` = half the short side), and reproduces the
outline exactly.  This is the default and covers the vast majority of v-widgets.

**Tile mode** (the caller passed ``image=``) — the slot is left to the caller's
image so ``image`` / ``compound`` / ``anchor`` behave *exactly* like native
tkinter (icon beside text, no overlap), and the corners are rounded by laying
four small tiles over them — each an exact crop of the same
:func:`~VIStk.Widgets._vWidget.rounded_pil_image` — plus thin edge strips that
carry the ``outline`` along the straight edges.

    The tiles are opaque ``r``×``r`` children, so they cover the extreme corners.
    That is fine for the modest radii icon buttons use, but at large radii the
    tiles swallow the content (at ``radius`` = half, four ``r``×``r`` tiles cover
    the *whole* widget).  Large radii / circles therefore need fill mode — i.e.
    no caller ``image=``.

The mixin is combined **before** ``vWidget`` so its ``_prepare_rounded`` /
``_render_rounded`` win in the MRO::

    class vLabel(RoundedLeaf, vWidget, Label):   ...
    class vButton(RoundedLeaf, vWidget, Button): ...

and it delegates fill mode straight back to ``vWidget`` via ``super()``.
"""

from __future__ import annotations

from tkinter import Label
import PIL.ImageTk
from VIStk.Widgets._vWidget import rounded_pil_image


class RoundedLeaf:
    """Rounded corners for a leaf widget: fill-in-slot by default, corner tiles
    when the caller needs the native image slot for their own ``image=``."""

    def _prepare_rounded(self) -> None:
        self._v_tiles: dict[str, Label] = {}
        self._v_strips: dict[str, Label] = {}
        # A caller image= means the slot is theirs -> tile mode.  Read it from the
        # native widget (it was passed through to super().__init__ untouched).
        try:
            self._v_tile_mode = bool(str(self.cget("image")))
        except Exception:
            self._v_tile_mode = False

        if self._v_tile_mode:
            # Native content keeps the slot; only flatten the chrome that would
            # otherwise show square corners.
            self.configure(bd=0, highlightthickness=0)
        else:
            # Fill mode: the proven image-slot fill (any radius, exact outline).
            super()._prepare_rounded()

    def _render_rounded(self, event=None) -> None:
        if not getattr(self, "_v_tile_mode", False):
            super()._render_rounded()          # vWidget paints the fill in-slot
            return

        w, h = self.winfo_width(), self.winfo_height()
        if w <= 1 or h <= 1 or (w, h) == self._v_last_size:
            return
        self._v_last_size = (w, h)

        r = self._effective_radius(w, h)
        fill = self._fill_color() or (255, 255, 255)
        corner = self._resolve_color(self._v_corner) or (240, 240, 240)
        outline = self._resolve_color(self._v_outline)
        ow = self._v_outline_width if (self._v_outline and outline) else 0

        full = rounded_pil_image(w, h, r, fill, corner,
                                 outline=outline, outline_width=ow)
        self._place_corner_tiles(full, w, h, r)
        self._place_edge_strips(full, w, h, r, self._border_band(full, w, h, fill, ow))

    # ── Overlay placement (tile mode only) ─────────────────────────────────────

    @staticmethod
    def _border_band(full, w: int, h: int, fill, ow: int) -> int:
        """How many pixels in from a straight edge actually differ from the flat
        fill — i.e. the outline *plus* its anti-aliasing.

        The outline is supersampled then Lanczos-downscaled, so it bleeds wider
        than ``outline_width``; strips of exactly ``ow`` px clipped it and left a
        broken/vanishing border.  Measured on the middle of the top edge (a
        straight run, clear of the corner arcs) so it is always exact.
        """
        if ow <= 0:
            return 0
        px = full.load()
        midx, band, limit = w // 2, 0, min(h // 2, ow + 8)
        for y in range(limit):
            if tuple(px[midx, y])[:3] != tuple(fill):
                band = y + 1
        return band

    def _place_corner_tiles(self, full, w: int, h: int, r: int) -> None:
        """Lay the four r×r rounded-corner crops over the widget's corners."""
        for name, (x, y) in (("tl", (0, 0)), ("tr", (w - r, 0)),
                             ("bl", (0, h - r)), ("br", (w - r, h - r))):
            if r <= 0:
                continue
            self._set_overlay(self._v_tiles, name,
                              full.crop((x, y, x + r, y + r)), x, y, r, r)

    def _place_edge_strips(self, full, w: int, h: int, r: int, band: int) -> None:
        """Carry the outline along the straight edges (only when an outline is
        drawn — without one the widget's own solid bg *is* the straight edge)."""
        wanted = {}
        if band > 0:
            wanted = {
                "top":    (r, 0, w - r, band),
                "bottom": (r, h - band, w - r, h),
                "left":   (0, r, band, h - r),
                "right":  (w - band, r, w, h - r),
            }
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
