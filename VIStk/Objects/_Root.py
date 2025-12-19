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
        self.exitAction = None
        self.exitArgs = None
        self.exitKwargs = None
    
    def unload(self):
        """Closes the window neatly for VIStk"""
        for element in self.winfo_children():
            try:
                element.destroy()
            except: pass
        
        self.Active = False
        self.destroy()

    def exitQueue(self, action, *args, **kwargs):
        """Sets a function to call in the exit loop. Use for redirects."""
        self.exitAction = action
        self.exitArgs = tuple(*args)
        self.exitKwargs = {**kwargs}

    def exitAct(self):
        """Executes the exitAction"""
        if not self.exitAction is None:
            if not self.exitArgs is None:
                if not self.exitKwargs is None:
                    self.exitAction(tuple(self.exitArgs),self.exitKwargs)
                else:
                    self.exitAction(tuple(self.exitArgs))
            else:
                if not self.exitKwargs is None:
                    self.exitAction(self.exitKwargs)
                else:
                    self.exitAction()