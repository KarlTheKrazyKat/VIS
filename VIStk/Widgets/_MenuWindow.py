from VIStk.Objects import *
from VIStk.Widgets._VISMenu import VISMenu
from tkinter import *

class MenuWindow(SubRoot):
    def __init__(self,parent:Tk|Toplevel,path:str,*args,center_ref=None,**kwargs):
        super().__init__(*args,**kwargs)
        self.master=parent

        #Hide until fully configured
        self.withdraw()

        #Load Menu
        self.menu = VISMenu(self, path)

        #SubWindow Geometry
        self.update()
        self.WindowGeometry.getGeometry(True)
        self.WindowGeometry.setGeometry(width=self.winfo_width(),
                                        height=self.winfo_height(),
                                        align="center",
                                        size_style="window_relative",
                                        window_ref=center_ref if center_ref is not None else parent)

        #Show after caller has finished setup (overrideredirect, bindings, etc.)
        self.after_idle(self._show)

    def _show(self):
        self.deiconify()
        self.focus_force()