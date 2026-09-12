from __future__ import annotations

from tkinter import *
from typing import Callable
from VIStk.Objects import Layout


class Tooltip:
    """Hover tooltip bound to a single widget."""
    def _init__(self, widget: Widget, text: str | Callable[[], str],
        *, delay: int = 500,
        wrap: int = 240,
        bg: str | None = None,
        fg: str | None = None,
        borderwidth: int = 1,
        anchor: str = "sw"):

        #Assign Arguments
        self.widget = widget
        self.delay = delay
        self.wrap  = wrap
        self.bg = bg or self.role("surface", "#f0f0f0")
        self.fg = fg or self.role("text", "#000000")
        self.bd = borderwidth
        self.anchor = anchor

        #Special assignment to resolve callables
        self.text = StringVar(value="")
        if callable(text):
            try: self.text.set(str(self.text()))
            except: pass
        else:
            self.text.set(text)

        #Not sure yet
        self.tip: Toplevel | None = None
        self.after_id: str | None = None

        widget.bind("<Enter>", self.on_enter, add="+")
        widget.bind("<Destroy>", self.on_destroy, add="+")

    def on_leave(self, _event=None) -> None:
        """Destroy tip on leave
        """
        self.cancel()

    def on_destroy(self, _event=None) -> None:
        if not self.tip is None: self.tip.destroy(); self.tip = None
        

    def show(self) -> None:
        #Tooltip Widget
        self.tip = Toplevel(self.widget)
        self.tip.withdraw()
        self.tip.overrideredirect(True)
        self.tip.attributes("-topmost", True)
        self.tip.Layout = Layout(self.tip)
        self.tip.Layout.colSize([1])
        self.tip.Layout.rowSize([1])
        self.tip.bind("<Leave>", self.tip.destroy, add="+")
        try: self.tip.attributes("-toolwindow", True)  #Win32 only
        except TclError: pass

        #Text Label
        lbl = Label(
            self.tip,
            textvariable=self.text,
            background=self.bg,
            foreground=self.fg,
            borderwidth=self.bd,
            relief="flat",
            wraplength=self.wrap,
            justify="left"
        )
        lbl.place(self.tip.Layout.cell(1,1))

        #Clear Idle Tasks
        self.tip.update_idletasks()

        #Cursor Position
        px = self.widget.winfo_pointerx()
        py = self.widget.winfo_pointery()
        x, y = px, py

        #Screen Bounds
        w, h = self.tip.winfo_reqwidth(), self.tip.winfo_reqheight()

        #Y Alignment
        match self.anchor[0]:
            case "n":
                pass #Aligned by default
            case "s":
                y -= h
            case _:
                y -= h//2

        #X Alignment
        match self.anchor[-1]:
            case "w":
                pass #Aligned by default
            case "e":
                x -= w
            case _:
                x -= h//2
        
        self.tip.geometry(f"+{x}+{y}")
        self.tip.deiconify()

    def destroy_tip(self) -> None:
        if self.tip is not None:
            try:
                self.tip.destroy()
            except TclError:
                pass
            self.tip = None
