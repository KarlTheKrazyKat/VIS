from tkinter import *
from tkinter import ttk
from VIStk.Widgets import MenuItem
from VIStk.fUtil import *

class VISMenu():
    """The menu class draws a column of buttons from a dict (typically a ``j_`` data module).

    Has two roots because can destroy both main window and subwindow on redirect.
    """
    def __init__(self, parent:Frame|LabelFrame|Toplevel|Tk, data:dict):
        """
        Args:
            parent: The parent widget to create menu items in.
            data (dict): Menu structure dict mapping keys to
                ``{"text": ..., "path": ..., "nav": ...}`` entries.
        """

        self.parent = parent
        """The Parent to Create `MenuItems` in"""
        self.root = self.parent.winfo_toplevel()
        """The Root of the Parent Object"""
        self.ob_dict = []
        """A Dictionary to Store `MenuItems` in"""
        self.n_dict = {}
        """A Dictionary to Store Navigation Controls in"""

        self.dict:dict = data
        self.parent.grid_columnconfigure(0,weight=1)
        for i in range(0, len(self.dict.keys()), 1):
            self.parent.grid_rowconfigure(i,weight=1)

        self.ob_dict:list[MenuItem]=[]
        """A `list` of `MenuItem` Objects"""
        x = 0
        for item in self.dict:
            ob = MenuItem(self.parent,
                      path= self.dict[item]["path"],
                      nav = self.dict[item]["nav"],
                      text = self.dict[item]["text"],
                      relief="flat",
                      font=fUtil.mkfont(10)
                      )
            ob.grid(row=x, column=0, sticky=(N,S,E,W))
            self.ob_dict.append(ob)
            self.n_dict[ob.nav]=ob
            x += 1

        if len(self.ob_dict) == 1:
            self.ob_dict[0].bind("<Configure>", lambda e: fUtil.autosize(e))
        if len(self.ob_dict) >1:
            self.ob_dict[0].bind("<Configure>", lambda e: fUtil.autosize(e,relations=self.ob_dict[1:]))
        self._kb_id = self.root.bind("<KeyPress>", self.menuNav, add="+")
        self.parent.bind("<Destroy>", self._on_destroy, add="+")

    def _on_destroy(self, event):
        if event.widget is self.parent:
            try:
                self.root.unbind("<KeyPress>", self._kb_id)
            except Exception:
                pass

    def menuNav(self,happ:Event):
        k=happ.char
        if self.n_dict.get(k) != None:
            self.n_dict[k].itemPath()
