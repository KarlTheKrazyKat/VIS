from tkinter import ttk
from tkinter import *


class SizeError(Exception):
    def __init__(self, message):
        self.message = message


class Layout():
    """A VIS Layout Manager for Frames and Windows"""
    def __init__(self, frame:ttk.Frame|Frame|LabelFrame|Tk|Toplevel):
        self.row = []
        self.column = []
 
    def cell(self,row:int,column:int)->dict:
        """Return the sizing attributes to place a cell

        Args:
            row (int): The row to place the widget in
            column (int): The column to place the widget in
        
        Returns:
            relheight (int): The relative height to the parent widget
            relwidth (int): The relative height to the parent widget
            relx (int): The relative x offset within the parent widget
            rely (int): The relative y offset within the parent widget
        """
        return {
            "relwidth": self.column[column],
            "relheight": self.row[row],
            "rely": self.row[row-1],
            "relx": self.column[column-1]
        }
    
    def rowSize(self, rows:list[float|int]):
        """Sets the size of rows for a Layout
        
        Args:
            rows (list[float|int]): The size of each individual row from 0.0 to 1.0
        """
        if sum(rows) == 1:
            if rows[0] == 0:
                self.row=rows
            else:
                self.row=rows
                self.row.insert(0,0)
        else:
            raise SizeError(f"Row sizes must sum to 1.0, not {sum(rows)}")
        
    def colSize(self, columns:list[float|int]):
        """Sets the size of columns for a Layout
        
        Args:
            columns (list[float|int]): The size of each individual column from 0.0 to 1.0
        """
        if sum(columns) == 1:
            if columns[0] == 0:
                self.column=columns
            else:
                self.column=columns
                self.column.insert(0,0)
        else:
            raise SizeError(f"Column sizes must sum to 1.0, not {sum(columns)}")