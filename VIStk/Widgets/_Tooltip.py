from __future__ import annotations

from tkinter import *
from typing import Callable
from VIStk.Objects import Layout

class Tooltip:
    """Hover tooltip bound to a single widget."""
    def __init__(self, widget: Widget, text: str | Callable[[], str] | StringVar,
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
        self.bg = bg or "#f0f0f0"
        self.fg = fg or "#000000"
        self.bd = borderwidth
        self.anchor = anchor
        self.funcid = None
        self.tip: Toplevel | None = None
        self.after = None

        #Special assignment to resolve callables
        if isinstance(text, Variable):
            self.text = text 
        else:
            self.text = StringVar(value="")
            if callable(text):
                try: self.text.set(str(text()))
                except: pass
            else:
                self.text.set(text)

        #Bindings
        widget.bind("<Enter>", self.on_enter, add="+")
        widget.bind("<Leave>", self.on_leave, add="+")
        widget.bind("<Destroy>", self.on_destroy, add="+")

    def on_enter(self, _event=None) -> None:
        self.funcid = self.widget.bind("<Motion>", self.check)

    def on_leave(self, _event=None) -> None:
        """Destroy tip on leave
        """
        if not self.funcid is None:
            self.widget.unbind("<Motion>", self.funcid, add="+")
        self.funcid=None

    def on_destroy(self, _event=None) -> None:
        if not self.tip is None: self.tip.destroy(); self.tip = None
        if not self.after is None: self.widget.after_cancel(self.after)

    def check(self, _event=None) -> None:
        if not self.after is None:
            self.widget.after_cancel(self.after)
        self.after = self.widget.after(self.delay,self.show)

    def show(self) -> None:
        if not self.tip is None: return None
        #Tooltip Widget
        self.tip = Toplevel(self.widget)
        self.tip.withdraw()
        self.tip.overrideredirect(True)
        self.tip.attributes("-topmost", True)
        self.tip.Layout = Layout(self.tip)
        self.tip.Layout.colSize([1])
        self.tip.Layout.rowSize([1])
        self.tip.bind("<Leave>", lambda e: self.destroy_tip(), add="+")
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

        #Window Size
        w, h = self.tip.winfo_reqwidth(), self.tip.winfo_reqheight()

        #Y Alignment
        match self.anchor[0]:
            case "n":
                y -= 1
            case "s":
                y -= h - 1
            case _:
                y -= h//2

        #X Alignment
        match self.anchor[-1]:
            case "w":
                x -= 1
            case "e":
                x -= w - 1
            case _:
                x -= w//2
        
        self.tip.geometry(f"{w}x{h}+{x}+{y}")
        self.tip.deiconify()

    def destroy_tip(self) -> None:
        if self.tip is not None:
            try:
                self.tip.destroy()
            except TclError:
                pass
            self.tip = None
