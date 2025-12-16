from tkinter import *
from VIStk.Objects._WindowGeometry import WindowGeometry
from VIStk.Objects._Window import Window

class Root(Tk, Window):
    """A wrapper for the Tk class with VIS attributes"""
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.WindowGeometry = WindowGeometry(self)

    def fullscreen(self):
        """Makes the window fullscreen"""