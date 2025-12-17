from tkinter import *
from VIStk.Objects._WindowGeometry import WindowGeometry
from VIStk.Objects._Window import Window

class Root(Tk, Window):
    """A wrapper for the Tk class with VIS attributes"""
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.WindowGeometry = WindowGeometry(self)
        self.Active = True
        self.protocol("WM_DELETE_WINDOW", self.unload)
    
    def unload(self):
        """Closes the window neatly for VIStk"""
        for element in self.winfo_children():
            try:
                element.destroy()
            except: pass
        
        self.Active = False