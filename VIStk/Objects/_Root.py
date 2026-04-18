from tkinter import *
from VIStk.Objects._Window import Window
from VIStk.Objects._WindowGeometry import *
from VIStk.Structures._Project import Project
from VIStk.Objects._Layout import Layout

class Root(Tk, Window):
    """A wrapper for the Tk class with VIS attributes"""
    def __init__(self,*args,project:bool=True,**kwargs):
        super().__init__(*args,**kwargs)
        self.WindowGeometry = WindowGeometry(self)
        self.Active:bool = True
        self.protocol("WM_DELETE_WINDOW", self.unload)
        self.exitAction = None
        self.exitArgs = None
        self.exitKwargs = None
        self.Project = Project() if project else None
        """The VIStk `Project`"""
        self.Layout=Layout(self)
        """The VIStk `Layout` of the Window"""
    
    def unload(self):
        """Closes the window neatly for VIStk"""
        self.Active = False
        for after_id in self.tk.call("after", "info"):
            try:
                self.after_cancel(after_id)
            except Exception: pass
        self.destroy()

    def exitQueue(self, action, *args, **kwargs):
        """Sets a function to call in the exit loop. Use for redirects."""
        self.exitAction = action
        self.exitArgs = args
        self.exitKwargs = kwargs

    def exitAct(self):
        """Executes the exitAction"""
        if self.exitAction is not None:
            args = self.exitArgs or ()
            kwargs = self.exitKwargs or {}
            self.exitAction(*args, **kwargs)

    def screenTitle(self, screen:str, title:str=None):
        """Sets the title and the screen that is currently active"""
        if title is None: title = screen
        self.title(title)
        self.Project.setScreen(screen)
    