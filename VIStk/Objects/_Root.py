from tkinter import *
from VIStk.Objects._Window import Window
from VIStk.Objects._WindowGeometry import *
from VIStk.Structures._Project import Project
from VIStk.Objects._Layout import Layout

class Root(Tk, Window):
    """A wrapper for the Tk class with VIS attributes"""
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.WindowGeometry = WindowGeometry(self)
        self.Active:bool = True
        self.protocol("WM_DELETE_WINDOW", self.unload)
        self.exitAction = None
        self.exitArgs = None
        self.exitKwargs = None
        self.Project = Project()
        self.Layout=Layout(self)
    
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

    def screenTitle(self, screen:str, title:str=None):
        """Sets the title and the screen that is currently active"""
        if title is None: title = screen
        self.title(title)
        self.Project.setScreen(screen)
    