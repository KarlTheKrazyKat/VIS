from tkinter import *
from tkinter import ttk
import os
import sys

class MenuItem():
    """Each item in the menu is created from the corresponding .json file. Each path should be given relative to xyz/WOM/
    """
    def __init__(self,parent:Frame|Toplevel|LabelFrame|Tk,path,nav,*args,**kwargs):
        """Create an item in a row on the menu
        Args:
            root (Tk): Master root for destruction on redirect
            _root (Toplevel): Toplevel object to create menu items in
            path (str): Name of .exe or absolute path to python script
            nav (str): Navigation character to click button
        """
        self.button = Button(master=parent, *args, **kwargs)
        self.parent = parent
        self.root = parent.winfo_toplevel()
        self.path = path
        self.nav = nav
        self.button.config(command = self.itemPath)
        enter = lambda event: event.widget.configure(background="dodger blue")
        leave = lambda event: event.widget.configure(background="gray94")
        self.button.bind("<Enter>", enter)
        self.button.bind("<Leave>", leave)
        #self.button.pack()

    def itemPath(self):
        """Opens the given path or exe for the button
        """
        #Should have a more VIStk way to switch screens
        if ".exe" in self.path:
            #os.execl(self.path,*(self.path))
            os.startfile(self.path)
        else:
            os.execl(sys.executable, *(sys.executable,self.path))
            #subprocess.call("pythonw.exe "+self.path)
        self.root.destroy()