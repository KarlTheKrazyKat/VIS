from VIStk.Objects import *
from VIStk.Widgets._VISMenu import VISMenu
from tkinter import *

class MenuWindow(SubRoot):
    def __init__(self,parent:Tk|Toplevel,path:str,*args,**kwargs):
        super().__init__(*args,**kwargs)

        #Ensure visibility
        self.focus_force()

        #Load Menu
        self.menu = VISMenu(self, path)
        
        #SubWindow Geometry
        self.update()
        self.WindowGeometry.getGeometry(True)
        self.WindowGeometry.setGeometry(width=self.winfo_width(),
                                        height=self.winfo_height(),
                                        align="center",
                                        size_style="window_relative",
                                        window_ref=parent)