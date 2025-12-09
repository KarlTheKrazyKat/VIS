from tkinter import *
from typing import Literal

query = Tk()
query.state("zoomed")
query.update()
ws = query.winfo_width()-2#Unclear about this offset
hs = query.winfo_height()-9#Might be operating system specific
query.destroy()
print(f"Screen has usable size of {ws}x{hs}")

class WindowGeometry():
    """Handles geometry relations and sizing/resizing for windows"""
    def __init__(self,window:Tk|Toplevel):
        """Creates a window geometry object and automatically extracts the size and location
        
        Args:
            window (Tk|Toplevel): The window to access geometry of
        """
        self.window:Tk|Toplevel = window
        self.getGeometry()
        window.WindowGeometry = self

    def getGeometry(self):
        """Sets the internal geometry of object to match the window"""
        geo_str = self.window.geometry()
        geo_list = geo_str.split("x")
        ng_list = [int(geo_list[0])]
        for i in geo_list[1].split("+"):
            ng_list.append(int(i))
        
        self.geometry = ng_list

    def setGeometry(self,width:int=None,height:int=None,x:int=None,y:int=None,align:Literal["center","n","ne","e","se","s","sw","w","nw"]=None,size_style:Literal["pixels","screen_relative"]=None):
        """Sets the geometry of the window"""
        if width is None: width = self.geometry[0]
        if height is None: height = self.geometry[1]

        #Check if aligning or using coordinates
        if align is None:
            if x is None: x = self.geometry[2]
            if y is None: y = self.geometry[3]
        else:
            x = None
            y = None
        

        #No adjustment needs to be made if pixels are given

        if size_style == "screen_relative":
            if not width == self.geometry[0]:
                width = ws*width/100
                
            if not height == self.geometry[1]:
                height = hs*height/100

        if not align is None:
            match align:
                case "center":
                    x = ws/2 - width/2
                    y = hs/2 - height/2
                case "n":
                    x = ws/2 - width/2
                    y = 0
                case "ne":
                    x = ws - width
                    y = 0
                case "e":
                    x = ws - width
                    y = hs/2 - height/2
                case "se":
                    x = ws - width
                    y = hs - height
                case "s":
                    x = ws/2 - width/2
                    y = hs - height
                case "sw":
                    x = 0
                    y = hs - height
                case "w":
                    x = 0
                    y = hs/2 - height/2
                case "nw":
                    x = 0
                    y = 0

        self.geometry = [int(width), int(height), int(x-7), int(y)]
        self.window.geometry('%dx%d+%d+%d' % tuple(self.geometry))