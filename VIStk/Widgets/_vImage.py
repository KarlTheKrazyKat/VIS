"""vImage (0.6.2) — a classic ``tk.Label`` that *only* holds an image, loaded
through the existing :class:`~VIStk.Objects._VIMG.VIMG` object, and (like the
rest of the v-family) inherits its parent's traits and can render rounded
corners.

Where :class:`~VIStk.Widgets.vLabel` is "text with an optional image", ``vImage``
is the mirror image: an image-only widget.  It hands path resolution and image
loading off to ``VIMG`` (so ``Project().p_images`` lookup, the glob fallback and
``absolute_path`` all behave identically to everywhere else ``VIMG`` is used) and
owns only the Tk rendering::

    pane = Frame(root, bg="white")

    # Contain a logo in the widget, letterboxed with the inherited white bg:
    vImage(pane, "logo").place(relwidth=1, relheight=1)

    # A fixed-size, rounded thumbnail (corners fall back to the parent bg):
    vImage(pane, "avatar.png", size=(64, 64), radius=12).pack()

* **Inheritance** — only ``background`` (an image carries its own pixels; there
  is no fg/font to inherit).  It defaults to the parent's background when
  omitted, so the aspect-ratio letterbox bars — and the transparent corners in
  rounded mode — blend into a solid-colour parent.  Anything passed explicitly
  wins.
* **Fit** — by default the image is *contained* in the live widget size,
  re-fitting on resize (the ``VIMG`` "fill" behaviour).  Pass ``size=(w, h)`` to
  contain it in a fixed pixel box instead, or ``fit=False`` to show it at its
  natural size.
* **Rounded corners** — opt in with ``radius`` > 0.  The corners are made
  transparent with an anti-aliased rounded mask, so the widget's (inherited)
  ``bg`` shows through and blends on a solid parent — recolouring the ``bg``
  re-blends with no re-render.  An optional ``outline`` strokes the rounded
  edge.  At ``radius=0`` it is an ordinary image ``Label``.

Note: like the other v-widgets, corner blending assumes a solid-colour parent.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from tkinter import Label
from PIL import Image, ImageChops, ImageDraw
from PIL.Image import Resampling
import PIL.ImageTk

from VIStk.Widgets._vWidget import vWidget
from VIStk.Objects._VIMG import VIMG

if TYPE_CHECKING:
    try:
        from typing import Unpack
    except ImportError:                       # Python < 3.11
        from typing_extensions import Unpack
    from tkinter import Misc
    from VIStk.Widgets._vtypes import _LabelKw


def round_image(img: "Image.Image", radius: int,
                outline: tuple[int, int, int] | None = None,
                outline_width: int = 0,
                supersample: int = 4) -> "Image.Image":
    """Return *img* with anti-aliased rounded corners (the corners made
    transparent) and an optional stroked *outline*.

    The rounded mask is multiplied into the image's own alpha, so transparency
    already present in the source (e.g. a PNG) is preserved.  Drawn at
    *supersample*× resolution and Lanczos-downscaled for smooth edges.  Colours
    are RGB 0-255 tuples (resolve Tk names with
    :meth:`~VIStk.Widgets._vWidget.vWidget._resolve_color` first).
    """
    img = img.convert("RGBA")
    w, h = img.size
    ss = max(1, int(supersample))
    r = max(0, min(int(radius), w // 2, h // 2))

    mask = Image.new("L", (w * ss, h * ss), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        (0, 0, w * ss - 1, h * ss - 1), radius=r * ss, fill=255)
    mask = mask.resize((w, h), resample=Resampling.LANCZOS)
    img.putalpha(ImageChops.multiply(mask, img.getchannel("A")))

    if outline is not None and outline_width > 0:
        big = Image.new("RGBA", (w * ss, h * ss), (0, 0, 0, 0))
        ImageDraw.Draw(big).rounded_rectangle(
            (0, 0, w * ss - 1, h * ss - 1), radius=r * ss,
            outline=(*outline, 255), width=outline_width * ss)
        img = Image.alpha_composite(img, big.resize((w, h),
                                                     resample=Resampling.LANCZOS))
    return img


class vImage(vWidget, Label):
    """A ``Label`` that holds an image (via ``VIMG``), inherits ``bg`` and can be
    rounded."""

    #: Only the background is meaningful for an image-only widget.
    _INHERIT = ("background",)

    def __init__(self, master: Misc | None = None, path: str | None = None, *,
                 image: "Image.Image | None" = None,
                 absolute_path: bool = False,
                 size: tuple[int, int] | list[int] | None = None,
                 fit: bool = True, radius: int = 0,
                 outline: str | None = None, outline_width: int = 1,
                 **kwargs: Unpack[_LabelKw]):
        """
        Args:
            master:        Parent widget.
            path:          Image path, resolved by :class:`VIMG`
                           (``Project().p_images`` + glob fallback unless
                           *absolute_path*).  ``None`` builds an empty holder;
                           call :meth:`set_path` / :meth:`set_image` later.
            image:         An **in-memory** ``PIL.Image.Image`` to display
                           instead of loading from disk (e.g. a generated image,
                           or ``Image.open(BytesIO(downloaded_bytes))``).  Takes
                           precedence over *path*; see :meth:`set_image`.
            absolute_path: Treat *path* as a literal filesystem path (no
                           ``p_images`` lookup).  Passed straight to ``VIMG``.
            size:          Fixed ``(w, h)`` box to contain the image in; omit to
                           contain it in the live widget size (see *fit*).
            fit:           When ``True`` (default) and no *size* is given, the
                           image is contained in the widget and re-fitted on
                           resize.  ``False`` shows it at its natural size.
            radius:        Corner radius in px; ``0`` (default) → square image.
            outline:       Optional border colour stroked on the rounded edge.
            outline_width: Border width in px (default ``1``; needs *outline*).
            **kwargs:      Any native :class:`tkinter.Label` option (see below).
                           ``bg`` is inherited from *master* when omitted; an
                           ``image=`` is ignored (the widget manages its own).
        """
        # vImage drives the image slot itself; never let a caller's image= or the
        # base rounded-fill machinery paint into it.  We pass radius=0 to the base
        # (so it stays a plain Label) and handle rounding image-side below.
        kwargs.pop("image", None)
        self._v_img_radius = int(radius or 0)
        self._v_img_outline_width = int(outline_width or 0)
        self._v_size = tuple(size) if size else None
        # A fixed size pins the box; otherwise fit fills the live widget.
        self._v_fit = bool(fit) and self._v_size is None
        self._v_photo = None                 # keep a ref so Tk won't GC it
        self._v_last_render = None           # debounce identical renders
        self._v_src = None                   # current PIL source image (disk or memory)
        self.VIMG: VIMG | None = None        # set only when loaded from disk

        # radius=0: the base stays a plain Label — vImage owns all rounding
        # image-side (transparent mask), so the base's outline/corner_bg are moot.
        super().__init__(master, radius=0, **kwargs)

        # Resolve the outline colour once (a winfo_rgb Tk round-trip) now that the
        # widget exists, instead of on every rounded re-fit.
        self._v_img_outline_rgb = self._resolve_color(outline)

        if image is not None:
            self.set_image(image)
        elif path is not None:
            self.set_path(path, absolute_path=absolute_path)

        # Re-fit on resize via the shared, clobber-proof render bindtag (so a
        # caller's bind("<Configure>") without add="+" can't stop it).  Fixed-box
        # and natural-size renders don't depend on widget size, so they paint once.
        # (Safe to install at radius=0: the bindtag just dispatches resize → re-fit.)
        if self._v_fit:
            self._install_render_binding()

    def set_path(self, path: str, *, absolute_path: bool = False) -> None:
        """Load (or swap) the image at *path* from disk and repaint immediately."""
        # VIMG is used as a loader only (path resolution + Image.open); vImage owns
        # the render, so don't hand it a fill target — its own <Configure> resize
        # would fight the clobber-proof render bindtag.
        self.VIMG = VIMG(self, path, absolute_path=absolute_path,
                         size=self._v_size)
        self._v_src = self.VIMG.Image
        self._v_last_render = None
        self._render()

    def set_image(self, image: "Image.Image") -> None:
        """Display (or swap to) an in-memory ``PIL.Image.Image`` — no disk load.

        Use for images that never touch disk: ones generated at runtime, decoded
        from bytes (``Image.open(BytesIO(data))``), or handed over from another
        library.  ``fit`` / ``size`` / ``radius`` all apply exactly as for a
        disk-loaded image.  Clears any ``VIMG`` from a previous :meth:`set_path`.
        """
        self.VIMG = None
        self._v_src = image
        self._v_last_render = None
        self._render()

    def _render(self, event=None) -> None:
        """Resize the source image to the current target box (contain), apply the
        optional rounded mask, and show it."""
        src = self._v_src
        if src is None:
            return
        iw, ih = src.size
        if not iw or not ih:
            return

        if self._v_size is not None:
            bw, bh = self._v_size
        elif self._v_fit:
            bw, bh = self.winfo_width(), self.winfo_height()
            if bw <= 1 or bh <= 1:           # not laid out yet — wait for resize
                return
        else:
            bw, bh = iw, ih

        scale = min(bw / iw, bh / ih)
        nw, nh = max(1, round(iw * scale)), max(1, round(ih * scale))

        # Skip the rebuild when the fitted size is unchanged.  set_path() resets
        # the key to None, so a same-size source swap still repaints.
        if (nw, nh) == self._v_last_render:
            return
        self._v_last_render = (nw, nh)

        img = src.resize((nw, nh), resample=Resampling.BICUBIC)
        if self._v_img_radius > 0:
            img = round_image(img, self._v_img_radius,
                              outline=self._v_img_outline_rgb,
                              outline_width=self._v_img_outline_width)
        self._v_photo = PIL.ImageTk.PhotoImage(img)
        self.configure(image=self._v_photo)

    # The clobber-proof <Configure> bindtag dispatches to _render_rounded; for an
    # image widget that just means "(re)fit the picture".
    _render_rounded = _render
