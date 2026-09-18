from __future__ import annotations

from tkinter import *
from tkinter import font
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

        #Built on the first show and kept, rather than rebuilt every time.  It
        #cannot be built here: the label takes its font from the option
        #database, and the pattern is resolved against the tip's own path, so
        #the only thing that can answer is the label itself.
        self.face = None

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
        if not self.funcid is None:
            self.widget.unbind("<Motion>", self.funcid)
        self.funcid = self.widget.bind("<Motion>", self.check, add="+")

    def on_leave(self, _event=None) -> None:
        """Destroy tip on leave
        """
        if not self.funcid is None:
            self.widget.unbind("<Motion>", self.funcid)
        self.funcid=None
        if not self.after is None: self.widget.after_cancel(self.after)
        self.after = None

    def on_destroy(self, _event=None) -> None:
        if not self.tip is None: self.tip.destroy(); self.tip = None
        try:
            if not self.after is None: self.widget.after_cancel(self.after)
        except: pass
        self.after = None

    def check(self, _event=None) -> None:
        if not self.after is None:
            self.widget.after_cancel(self.after)
        self.after = self.widget.after(self.delay,self.show)

    def show(self) -> None:
        if not self.tip is None: return None
        if not self.text.get(): return None   #nothing to say
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
            relief="solid",
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
        #The placer does not set a container's requested size, so the toplevel
        #cannot be asked how big the label made it -- the text is measured here
        #instead, wrapped the way the label will wrap it.
        if self.face is None:
            self.face = font.Font(font=lbl.cget("font"))

        lines = []
        for paragraph in self.text.get().split("\n"):
            line = ""
            for word in paragraph.split(" "):
                #Nothing can be done with a word wider than a whole line but
                #cut it, which is what the label does too.
                while self.face.measure(word) > self.wrap:
                    cut = 1
                    while (cut < len(word)
                           and self.face.measure(word[:cut + 1]) <= self.wrap):
                        cut += 1
                    if line:
                        lines.append(line)
                        line = ""
                    lines.append(word[:cut])
                    word = word[cut:]
                trial = f"{line} {word}" if line else word
                if line and self.face.measure(trial) > self.wrap:
                    lines.append(line)   #too wide with it, so it starts the next
                    line = word
                else:
                    line = trial
            lines.append(line)

        #The label's own chrome, on both sides of each axis.
        edge = int(lbl.cget("borderwidth")) + int(lbl.cget("highlightthickness"))
        w = (max((self.face.measure(line) for line in lines), default=0)
             + 2 * (edge + int(lbl.cget("padx"))))
        h = (self.face.metrics("linespace") * len(lines)
             + 2 * (edge + int(lbl.cget("pady"))))

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
