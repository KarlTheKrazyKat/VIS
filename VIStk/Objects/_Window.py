from tkinter import *
import PIL.Image
import PIL.ImageTk
import glob
from VIStk.Structures._Project import *

class Window:
    """A VIS Window object"""
    def __init__(self):
        """Initializes the VIS Window"""

    def fullscreen(self,absolute:bool=False):
        if absolute is False:
            try: #On Linux
                self.wm_attributes("-zoomed", True)
            except TclError: #On Windows
                self.state('zoomed')
        else:
            self.attributes("-fullscreen", True)

    def unfullscreen(self,absolute:bool=False):
        if absolute is False:
            try: #On Linux
                self.wm_attributes("-zoomed", False)
            except TclError: #On Windows
                self.state('normal')
        else:
            self.attributes("-fullscreen", False)

    def setIcon(self,icon:str):
        """Sets the window icon to an icon in ./Icons/
        
        Args:
            icon (str): The name of the icon excluding file extension (cat.png => cat)
        """
        project = Project()
        ficon = glob.glob(pathname=icon+".*",root_dir=project.p_project+"/Icons/")
        img = PIL.Image.open(project.p_project+"/Icons/"+ficon[0])
        imgtk = PIL.ImageTk.PhotoImage(img)
        self.iconphoto(False, imgtk)
        #Tkinter window will always be self for children