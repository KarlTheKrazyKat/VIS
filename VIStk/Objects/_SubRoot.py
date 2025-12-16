from tkinter import *
from VIStk.Objects._WindowGeometry import WindowGeometry
from VIStk.Objects._Window import Window

class SubRoot(Toplevel, Window):
    """A wrapper for the Toplevel class with VIS attributes"""
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.WindowGeometry = WindowGeometry(self)

    def modalize(self):
        """Makes the SubWindow modal"""
        self.focus_force()

        self.transient(self.master)
        self.grab_set()

        self.master.wait_window(self)