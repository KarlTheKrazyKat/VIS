from tkinter import *
from VIS.Objects._WindowGeometry import WindowGeometry

class SubRoot(Toplevel):
    """A wrapper for the Toplevel class with VIS attributes"""
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.WindowGeometry = WindowGeometry(self)