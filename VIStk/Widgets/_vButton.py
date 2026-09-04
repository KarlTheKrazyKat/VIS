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
* **Tk's own active state** — in rounded mode ``activebackground`` /
  ``activeforeground`` are mirrored from the resting ``bg`` / ``fg`` so Tk's
  built-in active rendering can't paint a square face over the rounded one; see
  :meth:`vButton._sync_active_colors`.  Pass either option explicitly to keep it.
* **Tk's own disabled state** — likewise, in rounded mode ``state`` and
  ``command`` are driven by the widget instead of by Tk, because Tk *stipples*
  any disabled button carrying an ``image`` and a rounded vButton always carries
  one.  ``cget("state")`` still reports what you set; see
  :meth:`vButton._v_apply_state`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from tkinter import Button, Label, TclError
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
    # ``state`` never reaches Tk in rounded mode (see _v_apply_state), so a
    # background change is the only native option that needs a tile repaint.
    _REPAINT_OPTS = ("background", "bg")
    #: Native colour options whose change must refresh the mirrored/greyed look.
    _COLOR_OPTS = ("background", "bg", "foreground", "fg")

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
        # may run on the first <Configure>) sees them.  Both are consumed here
        # rather than passed to Tk, so they come in through _v_set_color like
        # every other widget-held colour; super() registers the accumulated set.
        self._v_set_color("_v_active_fill", active_fill)
        self._v_set_color("_v_disabled_fill", disabled_fill)
        self._v_hover = False
        self._v_rest_bg = None            # the button's non-hover/non-disabled bg
        self._v_rest_fg = None            # ... and its non-disabled foreground
        self._v_rest_focus = ""           # ... and its pre-disable takefocus
        # ``state`` / ``command`` are the widget's in rounded mode: Tk must never
        # be handed state="disabled" (it would stipple the button), and it holds
        # _v_dispatch so every invoke path can be gated.  Taken straight out of
        # kwargs — the native __init__ below would otherwise reach Tcl unseen.
        self._v_state = "normal"
        self._v_command = None
        if int(radius or 0) > 0:
            self._v_state = str(kwargs.pop("state", "normal") or "normal")
            self._v_command = kwargs.pop("command", None)
            kwargs["command"] = self._v_dispatch
        super().__init__(master, radius=radius, radius_style=radius_style,
                         outline=outline,
                         outline_width=outline_width, corner_bg=corner_bg,
                         corners=corners, **kwargs)
        if self._v_radius > 0:
            self._v_rest_bg = self.cget("background")
            self._v_rest_fg = self.cget("foreground")
            self._v_rest_focus = super().cget("takefocus")
            self._sync_active_colors()
            if self._v_state != "normal":
                self._v_apply_state()
            if getattr(self, "_v_tile_mode", False):
                # Tile mode only: Tk stops painting the overlays once it enters
                # -state active, and never resumes — see _v_refresh_overlays.
                for sequence in self._OVERLAY_REFRESH_ON:
                    self.bind(sequence, self._v_queue_overlay_refresh, add="+")
            # The corners are painted away but the window is still rectangular,
            # so hit-test them: no hand cursor and no click out in the blank
            # triangle beyond the arc.
            self.bind("<Motion>", self._v_on_motion, add="+")
            self.bind("<Button-1>", self._v_gate_press, add="+")
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
        fill (the tiles are children, so they'd otherwise steal the events).

        The tiles sit exactly over the cut-off corners, so they carry the same
        rounded hit test as the button — the cursor starts neutral and
        :meth:`_v_on_motion` raises the hand only inside the arc."""
        overlay.bind("<ButtonRelease-1>", self._on_overlay_click, add="+")
        overlay.bind("<Motion>", self._v_on_motion, add="+")
        if self._v_active_fill:
            overlay.bind("<Enter>", self._on_enter, add="+")
            overlay.bind("<Leave>", self._on_leave, add="+")

    # ── Rounded hit testing: the corners are painted away, so treat them so ────

    def _v_point_inside(self, x: int, y: int) -> bool:
        """Is widget-relative (*x*, *y*) inside the **rounded** outline?

        A rounded v-widget is still a rectangular Tk window — only the painting
        is rounded — so without this the cut-off corners stay live: the hand
        cursor appears and clicks land in the blank triangle outside the arc.
        Each rounded corner is tested against its arc centre; square corners
        (per ``corners=``) and ``radius=0`` are always inside.
        """
        if getattr(self, "_v_radius", 0) <= 0:
            return True
        w, h = self.winfo_width(), self.winfo_height()
        if w <= 1 or h <= 1:
            return True
        if not (0 <= x < w and 0 <= y < h):
            return False
        r = self._effective_radius(w, h)
        if r <= 0:
            return True
        rounded = getattr(self, "_v_corners", None)
        # (centre x, centre y, index into the corners tuple) — the tuple order is
        # (top_left, top_right, bottom_right, bottom_left).
        for cx, cy, idx in ((r, r, 0), (w - r, r, 1),
                            (w - r, h - r, 2), (r, h - r, 3)):
            if rounded is not None and not rounded[idx]:
                continue
            # Only the corner's own quadrant can fall outside the arc.
            if (x < r if cx == r else x > w - r) and (y < r if cy == r else y > h - r):
                return (x - cx) ** 2 + (y - cy) ** 2 <= r * r
        return True

    def _v_pointer_inside(self, event=None) -> bool:
        """:meth:`_v_point_inside` for the pointer, wherever the event landed.

        Events arrive relative to the *tile* when the pointer is over an overlay
        child, so translate through the root rather than trusting ``event.x``.
        """
        try:
            if event is not None:
                x, y = event.x_root, event.y_root
            else:
                x, y = self.winfo_pointerxy()
            return self._v_point_inside(x - self.winfo_rootx(),
                                        y - self.winfo_rooty())
        except TclError:
            return False

    def _v_on_motion(self, event=None) -> None:
        """Raise the hand cursor — and light the hover fill — only inside the arc."""
        inside = self._v_pointer_inside(event)
        widget = getattr(event, "widget", None) or self
        wanted = "hand2" if (inside and self._v_state != "disabled") else ""
        try:
            if str(widget.cget("cursor")) != wanted:
                widget.configure(cursor=wanted)
        except TclError:
            return
        # Hold the hover fill to the same rule as the cursor.  ``<Enter>`` fires
        # once for the whole rectangle, so entering *through* a cut-off corner
        # would otherwise never light the fill — or would leave it lit out there.
        if self._v_active_fill:
            if inside and not self._v_hover:
                self._on_enter(event)
            elif not inside and self._v_hover:
                self._v_drop_hover()

    def _v_gate_press(self, event=None):
        """Swallow a press that landed in a cut-off corner.

        Returning ``"break"`` stops the ``Button`` class binding, so
        ``tk::ButtonDown`` never records the press and ``tk::ButtonUp`` never
        invokes — the click simply does not happen out there.
        """
        if not self._v_pointer_inside(event):
            return "break"

    # ── Tk's own active state: keep it from painting over the rounded look ─────

    #: ``(native active option, resting option)`` pairs mirrored in rounded mode.
    _ACTIVE_MIRROR = (("activebackground", "background"),
                      ("activeforeground", "foreground"))

    def _sync_active_colors(self) -> None:
        """Mirror the resting ``bg``/``fg`` onto ``activebackground`` /
        ``activeforeground``, so Tk's *active* state renders identically to rest.

        Tk paints those two options whenever the button's state is ``active`` —
        and it sets that state **itself, from Tcl**: ``tk::ButtonDown`` runs
        ``$w configure -relief sunken -state active`` on press, and on X11/Aqua
        ``tk::ButtonEnter`` does the same on plain hover.  Those are Tcl-level
        widget commands, so Python's :meth:`configure` never runs, the rounded
        fill / corner tiles are never repainted to match, and the native
        *square* face paints straight over the rounded one.

        It is not even transient: the state only returns to ``normal`` via
        ``tk::ButtonUp`` / ``tk::ButtonLeave``.  A drag that swallows the
        ``<ButtonRelease-1>`` — dragging a tab out of its bar — leaves the button
        stuck ``active``, so the rectangle stays for the widget's lifetime.

        Making the active colours equal to the resting ones removes the failure
        mode instead of trying to observe an event we never see.  A caller who
        passed either option explicitly keeps it (the same "explicit wins" rule
        as ``bg``/``fg`` inheritance); ``active_fill`` remains the supported way
        to colour hover, and this is a no-op at ``radius=0``.
        """
        explicit = getattr(self, "_v_explicit", ())
        for active_opt, rest_opt in self._ACTIVE_MIRROR:
            if active_opt in explicit:
                continue
            try:
                super().configure(**{active_opt: self.cget(rest_opt)})
            except TclError:
                pass

    # ── Tk's active state stops painting the overlays ──────────────────────────

    #: Events that bracket Tk's own ``-state`` changes (see _v_refresh_overlays).
    _OVERLAY_REFRESH_ON = ("<Button-1>", "<ButtonRelease-1>", "<Enter>", "<Leave>")

    def _v_refresh_overlays(self) -> None:
        """Re-assert the corner/edge overlays after Tk's active-state rendering.

        In **tile mode** the rounded artwork lives in overlay child widgets, and
        entering ``-state active`` stops Tk painting them — permanently.  They do
        not come back when the state returns to ``normal``, and Tk still reports
        them mapped, at the right geometry, holding the right images, so nothing
        about the widget's own state reveals the problem: the button simply goes
        square and stays square.  ``lift()`` does not recover it.

        Tk sets that state from Tcl — ``tk::ButtonDown`` on press, and
        ``tk::ButtonEnter`` on plain hover under X11/Aqua — so there is no
        Python-side call to intercept.  Re-setting each overlay's *existing*
        ``PhotoImage`` is what makes Tk draw it again; it costs ~0.4 ms and
        regenerates no artwork, where a full :meth:`_render_rounded` is ~13x
        dearer for the same result.

        Fill mode needs none of this — its rounded artwork is the button's own
        image, which Tk redraws in every state.
        """
        if not getattr(self, "_v_tile_mode", False):
            return
        try:
            # Leave the active state as well as repaint: while Tk is still in it
            # the overlays refuse to paint at all, so a held press would stay
            # square until release.  Nothing is lost — the colours are mirrored
            # (so active looked identical anyway) and tk::ButtonUp keys its
            # invoke off Priv(buttonWindow), not off -state.
            if str(super().cget("state")) == "active":
                super().configure(state="normal")
            # tk::ButtonDown also forces -relief sunken, ignoring the flat
            # overrelief this widget declares; on a flat rounded face that only
            # nudges the label a pixel on press.
            if str(super().cget("relief")) != "flat":
                super().configure(relief="flat")
            for overlay in (*self._v_tiles.values(), *self._v_strips.values()):
                image = getattr(overlay, "_v_img", None)
                if image is not None:
                    overlay.configure(image=image)
        except TclError:
            pass                     # destroyed before the idle callback ran

    def _v_queue_overlay_refresh(self, event=None) -> None:
        # after_idle so Tk's own class binding — the thing that changes -state —
        # has already run; an instance binding fires before the class one.
        try:
            self.after_idle(self._v_refresh_overlays)
        except TclError:
            pass

    # ── Disabled state: the widget's, not Tk's ─────────────────────────────────

    def _v_dispatch(self) -> None:
        """The real ``-command`` in rounded mode; gates the caller's callback.

        Every invoke path ends up running the widget's Tcl ``-command`` — a
        mouse click via ``tk::ButtonUp``, ``<space>``, ``<<Invoke>>``,
        :meth:`invoke` — so gating *here* covers all of them.  Overriding
        :meth:`invoke` would not: ``tk::ButtonUp`` calls the Tcl widget command
        directly and never sees a Python override.
        """
        if self._v_state == "disabled" or self._v_command is None:
            return
        self._v_command()

    def _v_disabled_fg(self) -> str | None:
        """The colour Tk would have greyed the text with — a caller's
        ``disabledforeground`` if given, else Tk's own ``SystemDisabledText``."""
        try:
            return str(super().cget("disabledforeground")) or None
        except TclError:
            return None

    def _v_apply_state(self) -> None:
        """Render the requested state ourselves, without Tk's ``-state``.

        Tk stipples **any** disabled button carrying an ``image``, whatever
        ``disabledforeground`` says — its test is ``disabledFg == NULL ||
        image != NULL`` — and a rounded vButton always carries one: the rounded
        fill in fill mode, the caller's icon in tile mode.  ``Button`` exposes no
        ``-stipple`` option to switch that off, so the only way to keep the
        rounded artwork clean is to never let Tk see ``state="disabled"`` and to
        reproduce what it would have done for us:

        =============================  =====================================
        what ``-state disabled`` does  what this does instead
        =============================  =====================================
        greys the text *and stipples*   ``foreground`` = ``disabledforeground``
        gates ``$w invoke``             :meth:`_v_dispatch` returns early
        drops out of tab traversal      ``takefocus=0`` (``tk::FocusOK`` → 0)
        =============================  =====================================

        Colours are applied through ``super().configure`` so :meth:`configure`'s
        resting-colour tracking does not record the *disabled* fill as the
        resting one — that would make re-enabling restore the greyed colour.
        """
        disabled = self._v_state == "disabled"
        opts = {"cursor": "arrow" if disabled else "hand2",
                "takefocus": 0 if disabled else self._v_rest_focus}
        fill = self._v_disabled_fill if disabled else self._v_rest_bg
        if fill is not None:
            opts["background"] = fill
        fg = self._v_disabled_fg() if disabled else self._v_rest_fg
        if fg:
            opts["foreground"] = fg
        try:
            super().configure(**opts)
        except TclError:
            return                        # destroyed mid-flight
        self._sync_active_colors()
        self._repaint_now()

    def cget(self, key):
        """Report the *requested* ``state`` / ``command`` in rounded mode.

        Tk's own ``-state`` is deliberately never ``disabled`` there (see
        :meth:`_v_apply_state`), and its ``-command`` is always
        :meth:`_v_dispatch`, so reading either back off the native widget would
        misreport what the caller set.
        """
        if getattr(self, "_v_radius", 0) > 0:
            if key == "state":
                return self._v_state
            if key == "command":
                return self._v_command
        return super().cget(key)

    # Misc binds __getitem__ to *its own* cget, so w["state"] would bypass ours.
    __getitem__ = cget

    # ── Hover / disabled: recolour the real bg; the tiles follow on repaint ─────

    def _on_enter(self, event=None) -> None:
        if self._v_hover or str(self.cget("state")) == "disabled":
            return
        # Only second-guess a *real* pointer event: called with no event this is
        # a deliberate programmatic hover, and the physical pointer is irrelevant.
        if event is not None and not self._v_pointer_inside(event):
            return          # entered through a cut-off corner; _v_on_motion will
        self._v_hover = True
        # configure(bg=) recolours the interior natively and forces a tile repaint.
        super().configure(background=self._v_active_fill)
        self._sync_active_colors()
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
        # A child's path is ours + "." + its name, so the separator has to be part
        # of the test: a bare prefix match also caught *siblings* (".!vbutton" is
        # a prefix of ".!vbutton2"), and moving between two vButtons in the same
        # parent left the first one stuck in hover — and, because configure()
        # stops tracking _v_rest_bg while _v_hover is set, stuck for good.
        me = str(self)
        if under is not None and (under is self or str(under).startswith(me + ".")):
            return                                  # still over the button / a tile
        self._v_drop_hover()

    def _v_drop_hover(self) -> None:
        """Return the button to its resting fill."""
        if not self._v_hover:
            return
        self._v_hover = False
        try:
            super().configure(background=self._v_rest_bg)
            self._sync_active_colors()
        except TclError:
            return                        # destroyed between <Leave> and the idle
        self._repaint_now()

    def _on_overlay_click(self, event=None) -> None:
        """A release over a corner/edge tile counts as a button click — but only
        where the tile is actually painted, not out in the cut-off corner."""
        if str(self.cget("state")) == "disabled":
            return
        if event is not None and not self._v_pointer_inside(event):
            return
        if self.winfo_containing(*self.winfo_pointerxy()) is not None:
            self.invoke()

    def _repaint_now(self) -> None:
        self._v_last_size = (0, 0)   # force a redraw at the current size
        self._render_rounded()

    @staticmethod
    def _v_take(cnf, kw, name):
        """Pop *name* out of whichever mapping carries it → ``(found, value)``."""
        if name in kw:
            return True, kw.pop(name)
        if isinstance(cnf, dict) and name in cnf:
            return True, cnf.pop(name)
        return False, None

    @staticmethod
    def _v_peek(cnf, kw, *names):
        """Read the first of *names* present, without removing it."""
        for name in names:
            if name in kw:
                return True, kw[name]
            if isinstance(cnf, dict) and name in cnf:
                return True, cnf[name]
        return False, None

    def configure(self, cnf=None, **kw):
        rounded = getattr(self, "_v_radius", 0) > 0
        had_state = state = None
        if rounded:
            if isinstance(cnf, dict):
                cnf = dict(cnf)               # never mutate the caller's dict
            had_state, state = self._v_take(cnf, kw, "state")
            had_command, command = self._v_take(cnf, kw, "command")
            if had_command:
                self._v_command = command     # Tk keeps holding _v_dispatch
        keys = set(kw) | (set(cnf) if isinstance(cnf, dict) else set())

        # Track the caller's resting colours so hover/disable can restore them.
        if rounded and not self._v_hover:
            found, value = self._v_peek(cnf, kw, "background", "bg")
            if found:
                self._v_rest_bg = value
        if rounded and self._v_state != "disabled":
            found, value = self._v_peek(cnf, kw, "foreground", "fg")
            if found:
                self._v_rest_fg = value

        result = super().configure(cnf, **kw)     # vWidget forces a tile repaint

        if had_state:
            self._v_state = str(state or "normal")
            self._v_apply_state()
        elif rounded and keys.intersection(self._COLOR_OPTS):
            if self._v_state == "disabled":
                self._v_apply_state()         # re-assert the greyed look over it
            else:
                # Anything that moved the resting colours has to move the mirrored
                # active colours too, or the mirror goes stale and Tk's active
                # rendering brings the square face back on the next press.
                self._sync_active_colors()
        return result

    config = configure
