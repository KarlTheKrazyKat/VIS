from tkinter import *

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