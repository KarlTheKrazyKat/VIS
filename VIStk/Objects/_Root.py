from tkinter import *
from VIStk.Objects._Window import Window
from VIStk.Objects._WindowGeometry import *
from VIStk.Structures.project import Project
from VIStk.Methods.sizing import *

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
        #self.bind("<Configure>", self.autosize)
        #self.bind("<<Modified>>", self.autosize)
    
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
    
    def size(self,rows:int,columns:int):
        """Sets the size of the grid
        
        Args:
            rows (int): The number of rows in the layout
            columns (int): The number of columns in the layout
        """
        size(self,rows,columns)

    def rowSize(self, row:int, weight:int=0, minsize:int=0, maxsize:int=None):
        """Sets sizing options for row
        
        Args:
            row (int): The row to set the size options for
            weight (int): The weight of the row when resizing
            minsize (int): The minimum size of the row
            maxsize (int): The maximum size of the row
        """
        rowSize(self,row,weight,minsize,maxsize)

    def colSize(self, column:int, weight:int=0, minsize:int=0, maxsize:int=None):
        """Sets sizing options for a column
        
        Args:
            row (int): The row to set the size options for
            weight (int): The weight of the row when resizing
            minsize (int): The minimum size of the row
            maxsize (int): The maximum size of the row
        """
        colSize(self,column,weight,minsize,maxsize)

    def autosize(self,*nonsense):
        """Resizing the layout according to the given rules"""
        autosize(self,*nonsense)
