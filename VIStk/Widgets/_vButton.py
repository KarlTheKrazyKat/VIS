"""vButton (0.6.3) — a classic ``tk.Button`` that inherits parent traits and
optionally renders rounded corners.

A drop-in replacement for :class:`tkinter.Button` (all native options and
methods, including ``command``/``invoke``, work unchanged) that adds the same
two conveniences as :class:`~VIStk.Widgets.vLabel`::

    bar = Frame(root, bg="white")
    vButton(bar, text="Save", command=save).pack()       # bg/fg/font inherited
    vButton(bar, text="Quote", command=quote, radius=8,  # rounded "chip"
            bg="#eef1f6", fg="#2f78d3",
            active_fill="#dbe6f6").pack()                 # hover fill

    vButton(bar, text="Save", image=icon, compound="left",  # icon beside text,
            radius=8).pack()                                # laid out natively

* **Inheritance** — ``background``/``foreground``/``font`` default to the
  parent's values when omitted; explicit options win.
* **Rounded corners** — opt in with ``radius`` > 0 (relief flattened, hand
  cursor; see :class:`~VIStk.Widgets._vLeaf.RoundedLeaf`).  A text-only button
  paints the rounded fill into its image slot and draws the label over it, so
  the text is never covered at *any* radius — including a true circle.  Passing
  your own ``image=`` switches to corner-tile rounding, which leaves the native
  image slot free so ``image`` / ``compound`` / ``anchor`` behave exactly like a
  native ``Button`` — an icon and text lay out side by side with no overlap
  (keep the radius modest in that mode — the tiles are opaque).  An optional
  ``active_fill`` recolours the button on hover (``<Enter>``/``<Leave>``) and
  ``disabled_fill`` greys it when ``state="disabled"`` (gating the click).  At
  ``radius=0`` it is an ordinary ``Button``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from tkinter import Button, Label
from VIStk.Widgets._vWidget import vWidget
from VIStk.Widgets._vLeaf import RoundedLeaf

if TYPE_CHECKING:
    try:
        from typing import Unpack
    except ImportError:                       # Python < 3.11
        from typing_extensions import Unpack
    from tkinter import Misc
    from VIStk.Widgets._vtypes import _ButtonKw


class vButton(RoundedLeaf, vWidget, Button):
    """A ``Button`` that inherits ``bg``/``fg``/``font`` and can be rounded."""

    _INHERIT = ("background", "foreground", "font")
    # A state change re-greys the button (and its corner tiles) — see configure.
    _REPAINT_OPTS = ("background", "bg", "state")

    def __init__(self, master: Misc | None = None, *,
                 radius: int = 0, radius_style: str = "pixels",
                 outline: str | None = None,
                 outline_width: int = 1, corner_bg: str | None = None,
                 corners: tuple[bool, bool, bool, bool] | None = None,
                 active_fill: str | None = None,
                 disabled_fill: str = "#e9ecef", **kwargs: Unpack[_ButtonKw]):
        """
        Args:
            master:        Parent widget.
            radius:        Corner radius; ``0`` (default) → plain Button.  Read as
                           pixels, or as a percentage per *radius_style*.
            radius_style:  ``"pixels"`` (default) → *radius* is a pixel radius;
                           ``"percent"`` → it is a percentage of the maximum
                           round (half the short side), so ``radius=100`` is a
                           full pill/circle at any size.  Re-resolved on every
                           resize.
            outline:       Optional border colour for the rounded edge.
            outline_width: Border width in px (default ``1``; needs *outline*).
            corner_bg:     Corner blend colour (defaults to the parent's bg).
            active_fill:   Optional hover fill colour (rounded mode only).
            disabled_fill: Fill painted when ``state="disabled"`` (rounded mode);
                           pair with ``configure(state=...)`` to grey the button.
            **kwargs:      Any native :class:`tkinter.Button` option (see below).
                           ``bg`` / ``fg`` / ``font`` are inherited from
                           *master* when omitted; ``image`` / ``compound`` behave
                           exactly as on a native Button.
        """
        # Hover / disabled state — set before super().__init__ so the render (which
        # may run on the first <Configure>) sees them.
        self._v_active_fill = active_fill
        self._v_disabled_fill = disabled_fill
        self._v_hover = False
        self._v_rest_bg = None            # the button's non-hover/non-disabled bg
        super().__init__(master, radius=radius, radius_style=radius_style,
                         outline=outline,
                         outline_width=outline_width, corner_bg=corner_bg,
                         corners=corners, **kwargs)
        if self._v_radius > 0:
            self._v_rest_bg = self.cget("background")
            if active_fill:
                self.bind("<Enter>", self._on_enter, add="+")
                self.bind("<Leave>", self._on_leave, add="+")

    # ── Rounded overrides ──────────────────────────────────────────────────────

    def _prepare_rounded(self) -> None:
        # RoundedLeaf zeroes the chrome and sets up the corner tiles; flatten the
        # relief so the tiles are the only edge treatment, and show a hand cursor.
        super()._prepare_rounded()
        self.configure(relief="flat", overrelief="flat", cursor="hand2")

    def _bind_overlay(self, overlay: Label) -> None:
        """Keep the corner/edge tiles clickable and hover-aware: a click on a
        corner still invokes the button, and hovering a corner keeps the hover
        fill (the tiles are children, so they'd otherwise steal the events)."""
        overlay.configure(cursor="hand2")
        overlay.bind("<ButtonRelease-1>", self._on_overlay_click, add="+")
        if self._v_active_fill:
            overlay.bind("<Enter>", self._on_enter, add="+")
            overlay.bind("<Leave>", self._on_leave, add="+")

    # ── Hover / disabled: recolour the real bg; the tiles follow on repaint ─────

    def _on_enter(self, event=None) -> None:
        if self._v_hover or str(self.cget("state")) == "disabled":
            return
        self._v_hover = True
        # configure(bg=) recolours the interior natively and forces a tile repaint.
        super().configure(background=self._v_active_fill)
        self._repaint_now()

    def _on_leave(self, event=None) -> None:
        # Fired when leaving the button OR crossing onto a child tile; only drop
        # hover once the pointer is truly outside the button and its tiles.
        self.after_idle(self._maybe_unhover)

    def _maybe_unhover(self) -> None:
        try:
            under = self.winfo_containing(*self.winfo_pointerxy())
        except Exception:
            under = None
        me = str(self)
        if under is not None and (under is self or str(under).startswith(me)):
            return                                  # still over the button / a tile
        if self._v_hover:
            self._v_hover = False
            super().configure(background=self._v_rest_bg)
            self._repaint_now()

    def _on_overlay_click(self, event=None) -> None:
        """A release over a corner/edge tile counts as a button click."""
        if str(self.cget("state")) == "disabled":
            return
        if self.winfo_containing(*self.winfo_pointerxy()) is not None:
            self.invoke()

    def _repaint_now(self) -> None:
        self._v_last_size = (0, 0)   # force a redraw at the current size
        self._render_rounded()

    def configure(self, cnf=None, **kw):
        keys = set(kw) | (set(cnf) if isinstance(cnf, dict) else set())
        # Track the caller's resting bg so hover/disabled can restore it, and
        # apply the disabled/normal fill to the real bg (tiles follow on repaint).
        bg_key = "background" if "background" in keys else ("bg" if "bg" in keys else None)
        if bg_key and not self._v_hover and getattr(self, "_v_radius", 0) > 0:
            self._v_rest_bg = kw.get(bg_key, cnf.get(bg_key) if isinstance(cnf, dict) else None)

        result = super().configure(cnf, **kw)     # vWidget forces a tile repaint

        if getattr(self, "_v_radius", 0) > 0 and "state" in keys:
            disabled = str(self.cget("state")) == "disabled"
            super().configure(cursor="arrow" if disabled else "hand2")
            target = self._v_disabled_fill if disabled else self._v_rest_bg
            if target is not None:
                super().configure(background=target)
            self._repaint_now()
        return result

    config = configure
