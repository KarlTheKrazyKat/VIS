from typing import Literal
from tkinter import *

class PopOutWindow():
    """An empty popout window"""
    def __init__(self, master:Tk, width:int,height:int,size_style:Literal["pixels","root_relative","screen_relative"],title:str):
        """Will create an empty popout window
        
        """
        pow_root = Toplevel(master)
        parent_geometry = master.geometry()


        match size_style:
            case _:
                parent_geometry

