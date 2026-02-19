from tkinter import ttk
from tkinter import *
import sys

class ScrollableFrame(ttk.Frame):
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
        
        self.canvas.bind_all("<MouseWheel>", self.scroll)

    def sizeFrame(self, event:Event):
        """Sizing the Frame"""
        canvas_width=self.master.winfo_width()
        canvas_height=self.master.winfo_height()
        self.canvas.config(width=canvas_width-17, height=canvas_height)
        self.canvas.itemconfig(self.sfid, width=canvas_width-17)

    def scroll(self, e:Event):
        """Scrolls the Window"""
        self.canvas.yview_scroll(int(-1*e.delta/120), "units")
