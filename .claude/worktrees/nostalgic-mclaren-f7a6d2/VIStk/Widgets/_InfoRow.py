import datetime
from tkinter import Frame, Label

_BG = "grey55"
_FG = "grey88"

_BANNER_BG = {
    "warn":  "#c29d3d",
    "error": "#b33a3a",
    "info":  "#3a77a8",
}


class InfoRow(Frame):
    """Status bar displayed at the bottom of the Host window.

    Shows the active screen name and version on the left, the project
    copyright string centred, and the app version + live FPS on the right.

    The copyright string is normalised at construction time to match the
    long-form ``Copyright © {year} by {owner}   All Rights Reserved.``
    convention used by the legacy AssetManager footer.  When the project's
    copyright field already contains the ``©`` symbol it is passed through
    verbatim so devs can opt out by setting a fully-formatted string.

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
            if raw:
                copyright_text = (
                    f"Copyright © {year} by {raw}   All Rights Reserved."
                )
            else:
                copyright_text = f"Copyright © {year}   All Rights Reserved."
        else:
            copyright_text = raw

        # ── App version ────────────────────────────────────────────────────────
        try:
            app_version = str(project.Version)
        except Exception:
            app_version = ""

        # Project portion of the left label — held constant across screen
        # changes so the user always sees what app they're in.  The screen
        # portion is appended in :meth:`set_screen`.
        self._project_label = (
            f"{project.title} {app_version}" if app_version else project.title
        )

        # ── Layout: screen label (left) | copyright (centre) | version+fps (right)
        self._screen_lbl = Label(
            self, text=self._project_label, bg=_BG, fg=_FG, anchor="w", padx=6
        )
        self._screen_lbl.pack(side="left")

        # Copyright is placed at the geometric centre of the row rather
        # than packed between the side labels — packing with expand=True
        # only centres within the gap, which drifts off-centre once the
        # side labels have unequal widths (and the project + screen long-
        # form left label makes that drift conspicuous).
        Label(self, text=copyright_text, bg=_BG, fg=_FG).place(
            relx=0.5, rely=0.5, anchor="center"
        )

        # Right side shows just the FPS counter — the project version
        # used to be duplicated here, but it now lives on the left in
        # ``_project_label``.
        self._fps_lbl = Label(
            self, text="0 fps", bg=_BG, fg=_FG, anchor="e", padx=6,
        )
        self._fps_lbl.pack(side="right")
        self._app_version = app_version

        # Banner state (for show_banner / _dismiss_banner)
        self._banner_frame: Frame | None = None
        self._banner_text_lbl: Label | None = None
        self._banner_after_id: str | None = None

    # ── Public API ─────────────────────────────────────────────────────────────

    def set_screen(self, name: str, version: str = "") -> None:
        """Update the screen portion of the left label.

        The project portion (``"<Project> <ver>"``) is held constant and
        only the screen portion changes between tabs.  Passing empty
        strings collapses the label back to just the project portion.
        """
        if name and version:
            text = f"{self._project_label} — {name} {version}"
        elif name:
            text = f"{self._project_label} — {name}"
        else:
            text = self._project_label
        self._screen_lbl.config(text=text)

    def set_fps(self, fps: float) -> None:
        """Update the FPS counter."""
        self._fps_lbl.config(text=f"{fps:.1f} fps")

    def show_banner(self, text: str, duration_ms: int = 5000,
                    level: str = "warn") -> None:
        """Show a transient inline message across the InfoRow.

        The banner overlays the normal InfoRow contents until the user
        dismisses it with the ✕ or the duration elapses. Used by the Host
        to explain why a navigation click could not open a screen (e.g.
        the screen was not included in this installation).

        ``level`` selects the background colour: ``"warn"`` (amber),
        ``"error"`` (red), or ``"info"`` (blue).

        Calling this while a banner is already visible replaces the text
        and resets the auto-dismiss timer rather than stacking.
        """
        bg = _BANNER_BG.get(level, _BANNER_BG["warn"])
        if self._banner_frame is not None:
            self._banner_text_lbl.config(text=text)
            self._banner_frame.config(bg=bg)
            self._banner_text_lbl.config(bg=bg)
            if self._banner_after_id is not None:
                try: self.after_cancel(self._banner_after_id)
                except Exception: pass
            self._banner_after_id = self.after(duration_ms, self._dismiss_banner)
            return

        self._banner_frame = Frame(self, bg=bg)
        self._banner_frame.place(relx=0, rely=0, relwidth=1, relheight=1)
        self._banner_text_lbl = Label(self._banner_frame, text=text, bg=bg,
                                      fg="white", anchor="w", padx=8)
        self._banner_text_lbl.pack(side="left", fill="both", expand=True)
        dismiss = Label(self._banner_frame, text="✕", bg=bg, fg="white",
                        cursor="hand2", padx=10)
        dismiss.pack(side="right")
        dismiss.bind("<Button-1>", lambda e: self._dismiss_banner())
        self._banner_after_id = self.after(duration_ms, self._dismiss_banner)

    def _dismiss_banner(self) -> None:
        # Guard against firing after the parent window has been destroyed —
        # show_banner schedules self.after() and Tk does not cancel pending
        # after-callbacks when a widget is destroyed.
        try:
            if not self.winfo_exists():
                return
        except Exception:
            return
        if self._banner_frame is not None:
            try: self._banner_frame.destroy()
            except Exception: pass
        self._banner_frame = None
        self._banner_text_lbl = None
        self._banner_after_id = None
