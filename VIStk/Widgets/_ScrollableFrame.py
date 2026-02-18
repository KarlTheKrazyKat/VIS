from tkinter import ttk
from tkinter import *

class ScrollableFrame(ttk.Frame):
    def __init__(self, root, *args, **kwargs):
        super().__init__(root, *args, **kwargs)
        self.canvas = Canvas(self,height=root.winfo_height(),width=root.winfo_width())
        """A `Canvas` to Fill the `Frame` and Scroll on"""
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        """The `ttk.Scrollbar`"""
        self.scrollable_frame = Frame(self.canvas)
        self.scrollable_frame.columnconfigure(0,weight=1)
        """The `ttk.Frame` to Scroll"""

        self.sfid = self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.bind("<Configure>", self.sizeFrame)

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(
                scrollregion=self.canvas.bbox("all")
            )
        )
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.canvas.grid(row=1,column=1,sticky=(N,S,E,W))
        self.scrollbar.grid(row=1,column=2,sticky=(N,S))

    def sizeFrame(self, event:Event):
        """Sizing the Child Frame"""
        canvas_width=event.width
        self.canvas.itemconfig(self.sfid, width=canvas_width-self.scrollbar.winfo_width())