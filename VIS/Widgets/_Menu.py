import json
from tkinter import *
from tkinter import ttk
from VIS.Widgets import MenuItem

class Menu():
    """The menu class drawings a column of buttons with subprocess calls to paths defined in a corresponding .json file.

    Has two roots because can destory both main window and subwindow on redirect.
    """
    def __init__(self, root:Tk, path:str, destroyOnRedirect:bool=True):
        """
        Args:
            root (Tk): Master root for destruction on redirect
            _root (Toplevel): Toplevel object to create menu on
            path (str): Path to .json file describing menu
            destroyOnRedirect (bool): If True the root window will be destroyed on redicet
        """
        root.focus_force()#use to force window into focus
        self.path = path
        self.n_dict = {}
        with open(path) as file:
            self.dict = json.load(file)


        for item in self.dict:

            ob = MenuItem(root,_root,
                      path= self.dict[item]["path"],
                      nav = self.dict[item]["nav"],
                      text = self.dict[item]["text"]
                      )
            ob.button.pack()
            self.n_dict[ob.nav]=ob

        root.bind("<KeyPress>",self.menuNav)
    
    def menuNav(self,happ):
        k=happ.char
        if self.n_dict.get(k) != None:
            self.n_dict[k].itemPath()
