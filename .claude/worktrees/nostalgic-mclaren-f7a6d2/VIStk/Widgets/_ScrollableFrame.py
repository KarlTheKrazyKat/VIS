from tkinter import ttk
from tkinter import *
import sys

class ScrollableFrame(ttk.Frame):
    _active = None  # class-level: which instance currently owns the scroll
    _is_linux = sys.platform == "linux"
    _bound = False  # class-level: whether the global scroll binding exists

    def __init__(self, root, *args, **kwargs):
        super().__init__(root, *args, **kwargs)
        self.canvas = Canvas(self)
        """A `Canvas` to Fill the `Frame` and Scroll on"""
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        """The `ttk.Scrollbar`"""
        self.scrollable_frame = Frame(self.canvas)
        self.scrollable_frame.columnconfigure(0,weight=1)
        """The `ttk.Frame` to Scroll"""

        self.sfid = self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        """The Object ID of the Window Drawn to the Canvas"""
        self.bind("<Configure>", self.sizeFrame)

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(
                scrollregion=self.canvas.bbox("all")
            )
        )
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


    def sizeFrame(self, event:Event):
        """Sizing the Frame"""
        canvas_width=event.width
        canvas_height=event.height
        self.canvas.config(width=canvas_width-17, height=canvas_height)
        self.canvas.itemconfig(self.sfid, width=canvas_width-17)

    def scroll(self, e:Event):
        """Scrolls the Window"""
        if ScrollableFrame._is_linux:
            direction = -1 if e.num == 4 else 1
            self.canvas.yview_scroll(direction, "units")
        else:
            self.canvas.yview_scroll(int(-1*e.delta/120), "units")
