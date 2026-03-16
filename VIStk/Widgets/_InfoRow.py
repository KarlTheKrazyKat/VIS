import datetime
from tkinter import Frame, Label

_BG = "grey55"
_FG = "grey88"


class InfoRow(Frame):
    """Status bar displayed at the bottom of the Host window.

    Shows the active screen name and version on the left, the project
    copyright string centred, and the app version + live FPS on the right.

    The copyright string is normalised at construction time: if it does not
    already contain the ``©`` symbol, the current year and ``©`` are
    automatically prepended (e.g. ``"© 2026  bmi CAD Services"``).

    Call :meth:`set_screen` whenever the active tab changes and
    :meth:`set_fps` once per FPS update (typically once per second).
    """

    def __init__(self, parent, project, **kwargs):
        kwargs.setdefault("bg", _BG)
        super().__init__(parent, **kwargs)

        # ── Copyright normalisation ────────────────────────────────────────────
        raw = (project.copyright or "").strip()
        if "©" not in raw:
            year = datetime.datetime.now().year
            copyright_text = f"© {year}  {raw}" if raw else f"© {year}"
        else:
            copyright_text = raw

        # ── App version ────────────────────────────────────────────────────────
        try:
            app_version = str(project.Version)
        except Exception:
            app_version = ""

        # ── Layout: screen label (left) | copyright (centre) | version+fps (right)
        self._screen_lbl = Label(
            self, text="", bg=_BG, fg=_FG, anchor="w", padx=6
        )
        self._screen_lbl.pack(side="left")

        Label(self, text=copyright_text, bg=_BG, fg=_FG, anchor="center").pack(
            side="left", expand=True
        )

        self._fps_lbl = Label(
            self,
            text=f"v{app_version}  |  0 fps" if app_version else "0 fps",
            bg=_BG,
            fg=_FG,
            anchor="e",
            padx=6,
        )
        self._fps_lbl.pack(side="right")
        self._app_version = app_version

    # ── Public API ─────────────────────────────────────────────────────────────

    def set_screen(self, name: str, version: str = "") -> None:
        """Update the screen label.  Pass empty strings to clear it."""
        text = f"{name}  v{version}" if name and version else name
        self._screen_lbl.config(text=text)

    def set_fps(self, fps: float) -> None:
        """Update the FPS counter."""
        if self._app_version:
            self._fps_lbl.config(text=f"v{self._app_version}  |  {fps:.1f} fps")
        else:
            self._fps_lbl.config(text=f"{fps:.1f} fps")
