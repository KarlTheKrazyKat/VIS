from tkinter import ttk
from tkinter import *
from math import isclose

class SizeError(Exception):
    def __init__(self, message):
        self.message = message


class Layout():
    """A VIS Layout Manager for Frames and Windows"""
    def __init__(self, frame:ttk.Frame|Frame|LabelFrame|Tk|Toplevel):
        self.row = []
        self.column = []
 
    def cell(self,row:int,column:int, rowspan:int=None, columnspan:int=None)->dict:
        """Return the sizing attributes to place a cell

        Args:
            row (int): The row to place the widget in
            column (int): The column to place the widget in
            rowspan (int): The number of rows to span
            columnspan (int): The number of columns to span
        
        Returns:
            relheight (int): The relative height to the parent widget
            relwidth (int): The relative height to the parent widget
            relx (int): The relative x offset within the parent widget
            rely (int): The relative y offset within the parent widget
        """
        if rowspan is None and columnspan is None:
            return {
                "relwidth": self.column[column],
                "relheight": self.row[row],
                "rely": sum(self.row[:row]),
                "relx": sum(self.column[:column])
            }
        else:
            rowsize=0
            columnsize=0
            if not rowspan is None:
                for i in range(row,row+rowspan,1):
                    rowsize += self.row[i]
            else:
                rowsize = self.row[row]

            if not columnspan is None:
                for i in range(column,column+columnspan,1):
                    columnsize += self.column[i]
            else:
                columnsize = self.column[column]
            
            return {
                "relwidth": columnsize,
                "relheight": rowsize,
                "rely": sum(self.row[:row]),
                "relx": sum(self.column[:column])
            }
    
    def rowSize(self, rows:list[float|int]):
        """Sets the size of rows for a Layout
        
        Args:
            rows (list[float|int]): The size of each individual row from 0.0 to 1.0
        """
        if isclose(sum(rows),1,abs_tol=0.00001):
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
        if isclose(sum(columns),1,abs_tol=0.00001):
            if columns[0] == 0:
                self.column=columns
            else:
                self.column=columns
                self.column.insert(0,0)
        else:
            raise SizeError(f"Column sizes must sum to 1.0, not {sum(columns)}")