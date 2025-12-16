from tkinter import *
from typing import Literal

query = Tk()
try: #On Linux
    query.wm_attributes("-zoomed", True)
except TclError: #On Windows
    query.state('zoomed')
query.update()
global hs, ws
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

    def getGeometry(self, respect_size:bool=False):
        """Sets the internal geometry of object to match the window"""
        geo_str = self.window.geometry()
        geo_list = geo_str.split("x")
        ng_list = [int(geo_list[0])]
        for i in geo_list[1].split("+"):
            ng_list.append(int(i))
        
        if respect_size:
            self.geometry = [self.window.winfo_width(), self.window.winfo_height(), ng_list[2], ng_list[3]]
        else:
            self.geometry = ng_list

    def stripGeometry(self,objects:tuple[Literal["w","h","x","y"]]|Literal["all"]):
        """Returns integer values of the requested items"""
        geo_str = self.window.geometry()
        geo_list = geo_str.split("x")
        ng_list = [int(geo_list[0])]
        for i in geo_list[1].split("+"):
            ng_list.append(int(i))
        
        geo_list = []
        if objects == "all":
            geo_list = ng_list
        else:
            if "w" in objects: geo_list.append(ng_list[0])
            if "h" in objects: geo_list.append(ng_list[1])
            if "x" in objects: geo_list.append(ng_list[2])
            if "y" in objects: geo_list.append(ng_list[3])

        return geo_list


    def setGeometry(self,width:int=None,height:int=None,x:int=None,y:int=None,align:Literal["center","n","ne","e","se","s","sw","w","nw"]=None,size_style:Literal["pixels","screen_relative","window_relative"]=None,window_ref:Tk|Toplevel=None):
        """Sets the geometry of the window"""
        global hs, ws
        ox, oy = 0, 0

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

        if size_style == "window_relative":
            if not window_ref is None:
                _ws = window_ref.winfo_width()
                _hs = window_ref.winfo_height()

                if not _ws is None: ws = _ws
                if not _hs is None: hs = _hs

                geo_ref = WindowGeometry(window_ref).stripGeometry(("x","y"))
                
                ox = geo_ref[0]
                oy = geo_ref[1]

            #Will always hand over relative sizing to screen relative
            size_style = "screen_relative"

        if size_style == "screen_relative":
            if not width == self.geometry[0]:
                width = ws*width/100
                
            if not height == self.geometry[1]:
                height = hs*height/100

        if not align is None:
            match align:
                case "center":
                    x = ws/2 - width/2 + ox
                    y = hs/2 - height/2 + oy
                case "n":
                    x = ws/2 - width/2 + ox
                    y = 0 + oy
                case "ne":
                    x = ws - width + ox
                    y = 0 + oy
                case "e":
                    x = ws - width + ox
                    y = hs/2 - height/2 + oy
                case "se":
                    x = ws - width + ox
                    y = hs - height + oy
                case "s":
                    x = ws/2 - width/2 + ox
                    y = hs - height + oy
                case "sw":
                    x = 0 + ox
                    y = hs - height + oy
                case "w":
                    x = 0 + ox
                    y = hs/2 - height/2 + oy
                case "nw":
                    x = 0 + ox
                    y = 0 + oy

        self.geometry = [int(width), int(height), int(x-7), int(y)]
        self.window.geometry('%dx%d+%d+%d' % tuple(self.geometry))