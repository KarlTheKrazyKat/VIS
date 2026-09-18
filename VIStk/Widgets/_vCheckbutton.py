"""vCheckbutton (0.6.5) — a classic ``tk.Checkbutton`` that inherits parent
traits, so it stops showing the scheme grey on a coloured surface.

A drop-in replacement for :class:`tkinter.Checkbutton` (all native options and
methods — ``variable``, ``command``, ``select``/``deselect``/``toggle``,
``invoke`` — work unchanged)::

    pane = Frame(root, bg="white")
    shown = BooleanVar(value=True)
    vCheckbutton(pane, text="Show closed", variable=shown).pack()

* **Inheritance** — ``background``, ``foreground`` and ``font`` default to the
  parent's values when omitted, exactly as on :class:`~VIStk.Widgets.vLabel`,
  and follow a later parent recolour.  Anything passed explicitly wins.
* **The three colours that would give the grey back** — a Checkbutton paints
  ``activebackground`` / ``activeforeground`` whenever the pointer is over it,
  and ``highlightbackground`` in its 1 px focus ring; all three default to the
  system scheme, so an inherited-``bg`` checkbutton still flashed grey on hover
  and wore a grey ring at rest.  They are mirrored from the resting ``bg`` / ``fg``
  unless the caller sets them (see :meth:`vCheckbutton._sync_mirrored_colors`).

The indicator box itself is left alone: ``selectcolor`` stays the system field
colour, which is what makes the box read as a box on any surface.  There is no
``radius`` — the widget draws no fill of its own to round.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from tkinter import Checkbutton, TclError
from VIStk.Widgets._vWidget import vWidget

if TYPE_CHECKING:
    try:
        from typing import Unpack
    except ImportError:                       # Python < 3.11
        from typing_extensions import Unpack
    from tkinter import Misc
    from VIStk.Widgets._vtypes import _CheckbuttonKw


class vCheckbutton(vWidget, Checkbutton):
    """A ``Checkbutton`` that inherits ``bg``/``fg``/``font`` from its parent."""

    _INHERIT = ("background", "foreground", "font")
    #: ``(mirrored option, option it follows)`` — see _sync_mirrored_colors.
    _MIRROR = (("activebackground", "background"),
               ("activeforeground", "foreground"),
               ("highlightbackground", "background"))
    #: Native options whose change must re-run the mirror.
    _COLOR_OPTS = ("background", "bg", "foreground", "fg")

    def __init__(self, master: Misc | None = None,
                 **kwargs: Unpack[_CheckbuttonKw]):
        """
        Args:
            master:   Parent widget.
            **kwargs: Any native :class:`tkinter.Checkbutton` option (see below).
                      ``bg`` / ``fg`` / ``font`` are inherited from *master* when
                      omitted, and ``activebackground`` / ``activeforeground`` /
                      ``highlightbackground`` follow the resting colours unless
                      passed explicitly.
        """
        super().__init__(master, **kwargs)
        self._sync_mirrored_colors()

    def _sync_mirrored_colors(self) -> None:
        """Point the hover and focus-ring colours at the resting ``bg`` / ``fg``.

        Tk paints ``activebackground`` / ``activeforeground`` for as long as the
        pointer is inside the widget, and fills the ``highlightthickness`` ring
        (1 px on a Checkbutton, unlike a Label's 0) with ``highlightbackground``.
        All three default to the system scheme, so inheriting only ``bg``/``fg``
        left the grey visible anyway — as a flash on hover, and as a permanent
        hairline border at rest.

        A caller who passed any of them keeps it, the same "explicit wins" rule
        as the inherited props themselves.  Re-run after every change to the
        resting colours (see :meth:`configure`), including the ones
        :meth:`~VIStk.Widgets.vWidget.refresh` makes when the parent is
        recoloured or the palette switches.
        """
        explicit = self._v_explicit
        for mirrored, source in self._MIRROR:
            if mirrored in explicit:
                continue
            try:
                super().configure(**{mirrored: self.cget(source)})
            except TclError:
                pass                      # destroyed mid-flight

    def configure(self, cnf=None, **kw):
        result = super().configure(cnf, **kw)
        keys = set(kw) | (set(cnf) if isinstance(cnf, dict) else set())
        if keys.intersection(self._COLOR_OPTS):
            self._sync_mirrored_colors()
        return result

    config = configure
