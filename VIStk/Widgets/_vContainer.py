"""RoundedContainer (0.6.2) — shared rounded-corner machinery for the
v-prefixed *container* widgets (:class:`~VIStk.Widgets.vFrame` and
:class:`~VIStk.Widgets.vLabelFrame`).

Both are native Tk containers (``Frame`` / ``LabelFrame``) combined with
:class:`~VIStk.Widgets._vWidget.vWidget`; the only difference between them is the
native base, so the rounding logic is identical and lives here once.  A
container mixes it in *before* ``vWidget`` so its ``_prepare_rounded`` /
``_render_rounded`` win in the MRO::

    class vFrame(RoundedContainer, vWidget, LayoutFrame):      ...
    class vLabelFrame(RoundedContainer, vWidget, LabelFrame):  ...

The rounded look is two layers, because a Tk child is an opaque rectangle with
no per-widget transparency:

1. A single anti-aliased rounded rectangle (fill + optional ``outline``) is
   painted onto a **lowered** background ``Label`` that fills the container.
2. Every child is **inset** off the edges (whatever geometry manager placed it)
   so its square corners stay inside the rounded ones, and any sub-pixel
   overhang that remains is patched with a tiny per-corner crop drawn *on the
   child* (see :meth:`_refresh_corner_marks`).

The mixin expects the host to provide (all set by ``vWidget.__init__``):
``_v_radius``, ``_v_outline``, ``_v_outline_width``, ``_v_corner``,
``_v_last_size``, ``_fill_color()``, ``_resolve_color()`` — and a ``.Layout``
(carrying ``.margin``).  Call :meth:`_setup_container` from the host
``__init__`` after ``super().__init__`` to initialise the rest.
"""

from __future__ import annotations

from math import ceil, floor, sqrt
from tkinter import Label
import PIL.ImageTk
from VIStk.Widgets._vWidget import rounded_pil_image

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


class RoundedContainer:
    """Rounded-fill + child-inset behaviour shared by vFrame and vLabelFrame."""

    def _setup_container(self, inset: int | None) -> None:
        """Initialise rounded-container state; call from the host ``__init__``
        after ``super().__init__`` (so ``_v_radius`` and ``.Layout`` exist)."""
        self._v_inset = inset
        self._v_border_pil = None     # last rendered border image (cropped for marks)
        self._v_eff_ow = 0            # effective outline width actually painted
        # Seed the margin from a pixel radius; a percentage one depends on the
        # size, which isn't known until the first render sets it properly.
        if self._v_radius > 0 and self._v_radius_style == "pixels":
            self.Layout.margin = self._inset_for(self._v_radius)

    def _skip_child(self, child) -> bool:
        """Children the rounded machinery must leave alone — the lowered
        background label here; subclasses extend it (e.g. ``vLabelFrame`` adds
        its title ``labelwidget``, which the native widget positions itself)."""
        return child is getattr(self, "_v_bg_label", None)

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
    # child is inset off the edges so its square corners stay inside the rounded
    # ones.  Any remaining sub-pixel overhang is patched per-corner ON the child
    # (see _refresh_corner_marks) — never with a big overlay that covers content.

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

        # Size-aware radius: clamped to the short side, and recomputed here on
        # every resize so a percentage radius_style tracks the frame.
        r = self._effective_radius(w, h)
        pil = rounded_pil_image(w, h, r, fill, corner,
                                outline=outline, outline_width=ow)
        self._v_border_pil = pil
        self._v_eff_ow = ow
        self._v_bg_image = PIL.ImageTk.PhotoImage(pil)
        self._v_bg_label.configure(image=self._v_bg_image)

        # Keep the inset size-aware too: the inset that keeps content off the
        # corner arc follows whatever radius was actually drawn.
        self.Layout.margin = self._inset_for(r)

        # Re-inset once children have settled at the new size (catches both a
        # margin change and any children added since the last render), then patch
        # any sub-pixel corner overhang.
        self.after_idle(self._reflow)

    # ── Sub-pixel corner patch (drawn ON each child, not on the frame) ─────────
    #
    # The inset is whole-pixel, so a child's corner can still land a fraction of
    # a pixel proud of the rounded border — its *fill* then shows where the
    # *outline* (or, with no outline, the corner background) should be, notching
    # the border.  We can't fix that on the frame: the border lives on the
    # lowered image *behind* the child, which the child covers at that pixel.  So
    # the patch is drawn **on the child** — a tiny Label, placed at the child's
    # own corner above its content, showing an exact crop of the border image for
    # that spot.  Where the crop is fill it is invisible (it matches the child);
    # where it is outline / corner-bg it restores the border.  Sized to the
    # actual overhang (≈ 1 px), so it never reaches the child's text.

    def _reflow(self) -> None:
        """Re-inset children, then (once their geometry has settled) repaint the
        corner patches that hide any sub-pixel overhang over the border."""
        self._reinset_children()
        try:
            self.update_idletasks()
        except Exception:
            return
        self._refresh_corner_marks()

    def _refresh_corner_marks(self) -> None:
        pil = self._v_border_pil
        if pil is None:
            return
        w, h = self.winfo_width(), self.winfo_height()
        r = self._effective_radius(w, h)
        if r <= 0:
            for child in self.winfo_children():
                self._clear_marks(child)
            return
        rf = max(0, r - getattr(self, "_v_eff_ow", 0))   # fill arc (inside outline)
        for child in self.winfo_children():
            if self._skip_child(child):
                continue
            if not child.winfo_ismapped():
                self._clear_marks(child)
                continue
            try:
                self._mark_child(child, w, h, r, rf, pil)
            except Exception:
                self._clear_marks(child)

    def _mark_child(self, child, w: int, h: int, r: int, rf: int, pil) -> None:
        """Patch each corner of *child* that overhangs the fill arc (radius *rf*,
        i.e. is sitting on the outline / corner background)."""
        x0, y0 = child.winfo_x(), child.winfo_y()
        x1, y1 = x0 + child.winfo_width(), y0 + child.winfo_height()
        rf2 = rf * rf
        # corner name, arc centre (acx, acy), child's outer corner (ox, oy),
        # direction into the child (dx, dy).
        specs = (
            ("tl", r,     r,     x0, y0,  1,  1),
            ("tr", w - r, r,     x1, y0, -1,  1),
            ("bl", r,     h - r, x0, y1,  1, -1),
            ("br", w - r, h - r, x1, y1, -1, -1),
        )
        for name, acx, acy, ox, oy, dx, dy in specs:
            # The child only meets this corner if its outer corner is in the
            # rounded quadrant, and only overhangs if that corner is outside the
            # fill arc (covering the outline / corner background).
            if (dx * (acx - ox) <= 0 or dy * (acy - oy) <= 0
                    or (ox - acx) ** 2 + (oy - acy) ** 2 <= rf2):
                self._hide_mark(child, name)
                continue
            # Where the child's two edges cross back inside the fill arc bounds
            # the overhang region; crop exactly that from the border image.
            sx = sqrt(max(0.0, rf2 - (oy - acy) ** 2))
            sy = sqrt(max(0.0, rf2 - (ox - acx) ** 2))
            xc, yc = acx - dx * sx, acy - dy * sy
            bx0, bx1 = (ox, xc) if ox <= xc else (xc, ox)
            by0, by1 = (oy, yc) if oy <= yc else (yc, oy)
            bx0, by0 = max(0, floor(bx0)), max(0, floor(by0))
            bx1, by1 = min(w, ceil(bx1)), min(h, ceil(by1))
            if bx1 <= bx0 or by1 <= by0:
                self._hide_mark(child, name)
                continue
            photo = PIL.ImageTk.PhotoImage(pil.crop((bx0, by0, bx1, by1)))
            mark = self._get_mark(child, name)
            mark._v_img = photo                         # keep a ref (no GC)
            mark.configure(image=photo)
            mark.place(x=bx0 - x0, y=by0 - y0,
                       width=bx1 - bx0, height=by1 - by0)
            mark.lift()

    @staticmethod
    def _get_mark(child, name) -> Label:
        marks = getattr(child, "_v_corner_marks", None)
        if marks is None:
            marks = child._v_corner_marks = {}
        mark = marks.get(name)
        if mark is None:
            mark = marks[name] = Label(child, bd=0, highlightthickness=0,
                                       takefocus=0)
        return mark

    @staticmethod
    def _hide_mark(child, name) -> None:
        marks = getattr(child, "_v_corner_marks", None)
        if marks and name in marks:
            marks[name].place_forget()

    @staticmethod
    def _clear_marks(child) -> None:
        marks = getattr(child, "_v_corner_marks", None)
        if marks:
            for mark in marks.values():
                mark.place_forget()

    # ── Child insetting (all geometry managers) ───────────────────────────────

    def _reinset_children(self) -> None:
        """Inset every child off the frame edges by the current `.Layout.margin`,
        whichever geometry manager placed it.  The inset is layered on top of the
        child's own geometry so the corner stays clear of square child corners;
        the lowered background label is skipped (it must fill the frame)."""
        m = self.Layout.margin
        for child in self.winfo_children():
            if self._skip_child(child):
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
