from tkinter import *
from VIStk.Objects._Window import Window
from VIStk.Objects._WindowGeometry import *
from VIStk.Objects._Layout import Layout

class SubRoot(Toplevel, Window):
    """A wrapper for the Toplevel class with VIS attributes"""
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.WindowGeometry = WindowGeometry(self)
        self.modal = False
        self.Layout=Layout(self)

    def modalize(self):
        """Makes the SubWindow modal"""
        #Cannot unmodalize a window. dont know if that makes sense?
        self.modal = True
        self.focus_force()

        self.transient(self.master)
        self.grab_set()

        self.master.wait_window(self)