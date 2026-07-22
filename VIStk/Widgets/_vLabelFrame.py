"""vLabelFrame (0.6.2) — a classic ``tk.LabelFrame`` that inherits parent traits
and optionally renders rounded corners.

A drop-in replacement for :class:`tkinter.LabelFrame` (every native option and
method works unchanged — ``text``, ``labelanchor``, ``labelwidget``, ``fg`` /
``font`` for the title, ``relief``, ``bd`` …) that adds the v-widget
conveniences shared with :class:`~VIStk.Widgets.vFrame`::

    box = vLabelFrame(root, text="Tooling", radius=12, outline="#c8ccd2")
    box.place(x=20, y=20, width=260, height=180)
    box.Layout.colSize([1.0]); box.Layout.rowSize([1.0])
    vLabel(box, text="Inside").place(box.Layout.cell(1, 1))

* **Inheritance** — ``background``, ``foreground`` and ``font`` default to the
  parent's values when omitted (the title uses ``fg`` / ``font``), so a box
  dropped into a styled parent blends in.  Anything passed explicitly wins.
* **Rounded corners** — opt in with ``radius`` > 0.  The native rectangular
  border is flattened and a single anti-aliased rounded rectangle (the frame's
  ``bg`` as **fill** + an optional ``outline``) is painted onto a *lowered*
  background ``Label``, and children are inset off the rounded corners.  See
  :class:`~VIStk.Widgets._vContainer.RoundedContainer` for the shared mechanism.

  A rounded box almost always wants an ``outline`` (or a fill that contrasts the
  parent) — otherwise the only thing drawn is the title.  At ``radius=0`` it is
  an ordinary ``LabelFrame``.

**How the title survives rounding.**  A ``LabelFrame`` lays its children out in a
*content area* below the title band, so a background image placed there would
miss the top/bottom border.  In rounded mode ``vLabelFrame`` instead floats the
background across the **whole** frame and keeps the title on top by routing it
through a ``labelwidget`` (an internal ``Label`` mirroring your ``text`` / ``fg``
/ ``font``, or the ``labelwidget`` you pass), which Tk still positions per
``labelanchor`` and which is lifted above the background — so the title breaks
the rounded border exactly like a native label.  ``configure(text=…)`` /
``cget("text")`` (and ``fg`` / ``foreground`` / ``font``) transparently proxy to
that title.  At ``radius=0`` none of this applies — it is a plain ``LabelFrame``.

Like ``vFrame`` it carries a ``.Layout`` helper, and children added at runtime
after the box is sized are inset on the next resize (or immediately via
:meth:`~VIStk.Widgets._vWidget.vWidget.refresh`).
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from tkinter import Label, LabelFrame
from VIStk.Objects._Layout import Layout
from VIStk.Widgets._vWidget import vWidget
from VIStk.Widgets._vContainer import RoundedContainer

if TYPE_CHECKING:
    try:
        from typing import Unpack
    except ImportError:                       # Python < 3.11
        from typing_extensions import Unpack
    from tkinter import Misc
    from VIStk.Widgets._vtypes import _LabelFrameKw


class vLabelFrame(RoundedContainer, vWidget, LabelFrame):
    """A ``LabelFrame`` that inherits ``bg``/``fg``/``font`` and can be rounded."""

    _INHERIT = ("background", "foreground", "font")

    #: Title options proxied to the internal title label in rounded mode.
    _TITLE_OPTS = ("text", "fg", "foreground", "font")

    def __init__(self, master: Misc | None = None, *,
                 radius: int = 0, radius_style: str = "pixels",
                 outline: str | None = None,
                 outline_width: int = 1, corner_bg: str | None = None,
                 inset: int | None = None, **kwargs: Unpack[_LabelFrameKw]):
        """
        Args:
            master:        Parent widget.
            radius:        Corner radius; ``0`` (default) → plain
                           ``LabelFrame``.  Read as pixels, or as a percentage
                           per *radius_style*.
            radius_style:  ``"pixels"`` (default) → *radius* is a pixel radius;
                           ``"percent"`` → it is a percentage of the maximum
                           round (half the short side), so ``radius=100`` is a
                           full pill/circle at any size.  Re-resolved on every
                           resize (the content inset follows it).
            outline:       Border colour for the rounded box (strongly
                           recommended in rounded mode — it draws the group box).
            outline_width: Border width in px (default ``1``; needs *outline*).
            corner_bg:     Corner blend colour (defaults to the parent's bg).
            inset:         Content inset (`.Layout.margin`) in px applied to every
                           child, however it is placed.  ``None`` (default)
                           auto-computes ``ceil(radius·(1 − 1/√2))`` — the largest
                           rectangle that fits inside the corner arc.  Invisible
                           when the child shares the box's fill.  ``0`` disables.
            **kwargs:      Any native :class:`tkinter.LabelFrame` option (see
                           below): ``text``, ``labelanchor``, ``labelwidget`` …
                           ``bg`` / ``fg`` / ``font`` are inherited from *master*
                           when omitted; ``bg`` is the rounded fill colour.
        """
        self._v_title = None        # internal title Label (rounded + text mode)
        super().__init__(master, radius=radius, radius_style=radius_style,
                         outline=outline,
                         outline_width=outline_width, corner_bg=corner_bg,
                         **kwargs)
        # LabelFrame is not a LayoutFrame, so attach the Layout helper directly
        # (the shared rounded machinery insets children via self.Layout.margin).
        self.Layout = Layout(self)
        self._setup_container(inset)
        if self._v_radius > 0:
            self._ensure_title()    # mirror text/fg/font onto a liftable label

    # ── Rounded overrides ──────────────────────────────────────────────────────

    def _prepare_rounded(self) -> None:
        # Lowered rounded-fill image (shared), then flatten the native
        # rectangular border so the rounded outline is the only visible chrome.
        super()._prepare_rounded()
        self.configure(bd=0, relief="flat", highlightthickness=0)

    def _render_rounded(self, event=None) -> None:
        w, h = self.winfo_width(), self.winfo_height()
        if w <= 1 or h <= 1 or (w, h) == self._v_last_size:
            return
        super()._render_rounded(event)   # paints the full-size image on the bg label
        # A LabelFrame's content area is offset by the title band, so the lowered
        # label (placed relative to it) misses the top/bottom border.  Float it
        # across the whole frame instead, and keep the title above it.
        self._cover_full_frame()

    def _cover_full_frame(self) -> None:
        """Re-place the lowered background label to span the entire frame (not
        just the title-offset content area) and lift the title above it."""
        bg = getattr(self, "_v_bg_label", None)
        if bg is None:
            return
        try:
            bg.place(x=0, y=0, relwidth=1, relheight=1)   # content area, to measure
            self.update_idletasks()
            cx, cy = bg.winfo_x(), bg.winfo_y()           # content origin in frame
            w, h = self.winfo_width(), self.winfo_height()
            # Clear the relative size or place() merges it with the absolute one
            # (relwidth=1 + width=w would double the label).
            bg.place(x=-cx, y=-cy, width=w, height=h, relwidth=0, relheight=0)
            bg.lower()
        except Exception:
            return
        title = self._title_widget()
        if title is not None:
            title.lift()

    def _skip_child(self, child) -> bool:
        # Leave the native title widget alone — the LabelFrame positions it
        # itself (per labelanchor); it must not be inset or corner-patched.
        return super()._skip_child(child) or child is self._title_widget()

    # ── Title management (rounded mode) ─────────────────────────────────────────

    def _title_widget(self):
        """The current ``labelwidget`` as a widget object, or ``None``."""
        try:
            name = LabelFrame.cget(self, "labelwidget")
        except Exception:
            return None
        if not name:
            return None
        try:
            return self.nametowidget(name)
        except Exception:
            return None

    def _ensure_title(self) -> Label | None:
        """In rounded mode, make sure the title is a liftable widget.

        If the caller supplied their own ``labelwidget`` it is used as-is.
        Otherwise, when there is title ``text``, an internal ``Label`` mirroring
        the native ``text`` / ``fg`` / ``font`` is created and installed as the
        ``labelwidget`` (so it draws above the background image and Tk keeps
        positioning it per ``labelanchor``)."""
        if self._v_radius <= 0:
            return None
        if self._v_title is not None:
            return self._v_title
        if self._title_widget() is not None:       # caller-supplied labelwidget
            return None
        if not LabelFrame.cget(self, "text"):      # nothing to show yet
            return None
        fill = LabelFrame.cget(self, "background")
        self._v_title = Label(self, text=LabelFrame.cget(self, "text"),
                              fg=LabelFrame.cget(self, "fg"),
                              font=LabelFrame.cget(self, "font"),
                              bg=fill, bd=0, highlightthickness=0, takefocus=0)
        LabelFrame.configure(self, labelwidget=self._v_title)
        return self._v_title

    def configure(self, cnf=None, **kw):
        """Native ``configure`` that, in rounded mode, routes title options
        (``text`` / ``fg`` / ``foreground`` / ``font``) to the internal title
        label and keeps that label's background in sync with the fill."""
        if self._v_radius <= 0 or getattr(self, "_v_title", None) is None:
            # Plain mode, or no internal title yet — but a title option may now
            # warrant creating one (rounded + text set after construction).
            result = super().configure(cnf, **kw)
            if self._v_radius > 0 and self._v_title is None:
                opts = set(kw) | (set(cnf) if isinstance(cnf, dict) else set())
                if opts.intersection(self._TITLE_OPTS):
                    self._ensure_title()
            return result

        opts = dict(cnf) if isinstance(cnf, dict) else {}
        opts.update(kw)
        title_kw = {("fg" if k == "foreground" else k): opts.pop(k)
                    for k in list(opts) if k in self._TITLE_OPTS}
        if title_kw:
            self._v_title.configure(**title_kw)
        if "background" in opts or "bg" in opts:     # keep the title chip on-fill
            try:
                self._v_title.configure(bg=opts.get("bg", opts.get("background")))
            except Exception:
                pass
        return super().configure(opts) if opts else None

    config = configure

    def cget(self, key):
        """Mirror of :meth:`configure` — title options read back from the
        internal title label when one is in use (rounded mode)."""
        if getattr(self, "_v_title", None) is not None and key in self._TITLE_OPTS:
            return self._v_title.cget("fg" if key == "foreground" else key)
        return super().cget(key)

    __getitem__ = cget
