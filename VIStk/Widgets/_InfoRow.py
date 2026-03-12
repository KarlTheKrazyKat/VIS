from tkinter import Frame, Label

_BG = "grey55"
_FG = "grey88"


class InfoRow(Frame):
    """Status bar displayed at the bottom of the Host window.

    Shows the active screen name and version on the left, the project
    copyright string centred, and the live frames-per-second on the right.

    Call :meth:`set_screen` whenever the active tab changes and
    :meth:`set_fps` once per FPS update (typically once per second).
    """

    def __init__(self, parent, project, **kwargs):
        kwargs.setdefault("bg", _BG)
        super().__init__(parent, **kwargs)

        copyright_text = project.copyright or ""

        self._screen_lbl = Label(
            self, text="", bg=_BG, fg=_FG, anchor="w", padx=6
        )
        self._screen_lbl.pack(side="left")

        Label(self, text=copyright_text, bg=_BG, fg=_FG, anchor="center").pack(
            side="left", expand=True
        )

        self._fps_lbl = Label(
            self, text="0 fps", bg=_BG, fg=_FG, anchor="e", padx=6
        )
        self._fps_lbl.pack(side="right")

    # ── Public API ─────────────────────────────────────────────────────────────

    def set_screen(self, name: str, version: str = "") -> None:
        """Update the screen label.  Pass empty strings to clear it."""
        text = f"{name}  v{version}" if name and version else name
        self._screen_lbl.config(text=text)

    def set_fps(self, fps: float) -> None:
        """Update the FPS counter."""
        self._fps_lbl.config(text=f"{fps:.1f} fps")
