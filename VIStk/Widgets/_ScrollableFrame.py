from tkinter import ttk
from tkinter import *
import sys

class ScrollableFrame(ttk.Frame):
    _active = None  # class-level: which instance currently owns the scroll
    _is_linux = sys.platform == "linux"
    _bound = False  # class-level: whether the global scroll binding exists

    WHEEL_STEP = 60    # pixels travelled per mouse-wheel notch
    _ANIM_MS = 15      # animation frame interval (~66 fps)
    _EASE = 0.30       # fraction of the remaining distance moved each frame

    def __init__(self, root, *args, **kwargs):
        super().__init__(root, *args, **kwargs)
        self.canvas = Canvas(self)
        """A `Canvas` to Fill the `Frame` and Scroll on"""
        # yscrollincrement=1 makes a "units" scroll equal exactly one pixel.
        # Without it Tk treats one unit as a tenth of the canvas height, so each
        # wheel notch jumps ~10% of the viewport in a single hop (the "choppy"
        # feel). Pixel units let us move a small, consistent amount per notch
        # and ease it across frames for smooth scrolling.
        self.canvas.configure(yscrollincrement=1)
        self._scroll_remaining = 0.0  # pixels still to travel (signed)
        self._scroll_anim = None      # pending after() id, or None when idle
        self._scrollregion_job = None # pending scrollregion recompute, or None
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        """The `ttk.Scrollbar`"""
        self.scrollable_frame = Frame(self.canvas)
        self.scrollable_frame.columnconfigure(0,weight=1)
        """The `ttk.Frame` to Scroll"""

        self.sfid = self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        """The Object ID of the Window Drawn to the Canvas"""
        self.bind("<Configure>", self.sizeFrame)

        self.scrollable_frame.bind("<Configure>", self._on_inner_configure)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.canvas.pack(side="left",fill="both",expand=True)
        self.scrollbar.pack(side="right",fill="y")

        self.canvas.bind("<Enter>", self._on_enter)
        self.canvas.bind("<Leave>", self._on_leave)

        if not ScrollableFrame._bound:
            ScrollableFrame._bind_scroll_global(self.canvas)

    @classmethod
    def _bind_scroll_global(cls, canvas):
        if cls._is_linux:
            canvas.bind_all("<Button-4>", cls._dispatch_scroll)
            canvas.bind_all("<Button-5>", cls._dispatch_scroll)
        else:
            canvas.bind_all("<MouseWheel>", cls._dispatch_scroll)
        cls._bound = True

    def _on_enter(self, event):
        ScrollableFrame._active = self

    def _on_leave(self, event):
        if ScrollableFrame._active is self:
            ScrollableFrame._active = None

    @staticmethod
    def _dispatch_scroll(event):
        active = ScrollableFrame._active
        if active is not None:
            active.scroll(event)


    def _on_inner_configure(self, event=None):
        """Queue a single scrollregion recompute for the current idle cycle.

        A burst of `<Configure>` events — e.g. a collapsing group that resizes
        many rows at once — would otherwise run `bbox("all")` over every widget
        on each intermediate resize. Coalescing them into one recompute at idle
        keeps collapse/expand snappy on large frames.
        """
        if self._scrollregion_job is None:
            self._scrollregion_job = self.after_idle(self._sync_scrollregion)

    def _sync_scrollregion(self):
        """Recompute the canvas scrollregion from the current content bounds."""
        self._scrollregion_job = None
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def sizeFrame(self, event:Event):
        """Sizing the Frame"""
        canvas_width=event.width
        canvas_height=event.height
        self.canvas.config(width=canvas_width-17, height=canvas_height)
        self.canvas.itemconfig(self.sfid, width=canvas_width-17)

    def scroll(self, e:Event):
        """Queue a smooth, eased scroll in response to a wheel notch."""
        if ScrollableFrame._is_linux:
            notches = -1 if e.num == 4 else 1
        else:
            notches = int(-1 * e.delta / 120)
        if not notches:
            return
        # Accumulate into the outstanding distance so rapid notches coalesce
        # into one continuous glide instead of fighting each other.
        self._scroll_remaining += notches * self.WHEEL_STEP
        if self._scroll_anim is None:
            self._tick_scroll()

    def _tick_scroll(self):
        """Move a fraction of the remaining distance, then reschedule."""
        remaining = self._scroll_remaining
        if abs(remaining) < 1:
            self._scroll_remaining = 0.0
            self._scroll_anim = None
            return
        move = remaining * self._EASE
        move = int(move) if abs(move) >= 1 else (1 if remaining > 0 else -1)
        before = self.canvas.yview()[0]
        self.canvas.yview_scroll(move, "units")  # units == pixels (increment=1)
        if self.canvas.yview()[0] == before:
            # Hit the top or bottom edge — drop the rest so we don't spin.
            self._scroll_remaining = 0.0
            self._scroll_anim = None
            return
        self._scroll_remaining -= move
        self._scroll_anim = self.canvas.after(self._ANIM_MS, self._tick_scroll)
