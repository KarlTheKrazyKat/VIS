from tkinter import ttk
from VIStk.Methods.sizing import *

class Layout(ttk.Frame):
    """A VIS Layout Frame"""
    def __init__(self, *args, **kwargs):
        super().__init__(*args,**kwargs)
        
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
