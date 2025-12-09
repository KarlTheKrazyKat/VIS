from tkinter import *
from VIS.Objects._WindowGeometry import WindowGeometry

class Root(Tk):
    """A wrapper for the Tk class with VIS attributes"""
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.WindowGeometry = WindowGeometry(self)