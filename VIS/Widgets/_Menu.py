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
        #Popout Window
        root.focus_force()#use to force window into focus
        self.root = root
        self.menu_root = Toplevel(root)
        self.menu_root.focus_force()
        self.path = path
        self.ob_dict = []
        self.n_dict = {}
        with open(path) as file:
            self.dict = json.load(file)


        for item in self.dict:

            ob = MenuItem(root,
                      path= self.dict[item]["path"],
                      nav = self.dict[item]["nav"],
                      text = self.dict[item]["text"]
                      )
            ob.button.pack()
            self.ob_dict.append(ob)
            self.n_dict[ob.nav]=ob

        root.bind("<KeyPress>",self.menuNav)
    
    def menuNav(self,happ):
        k=happ.char
        if self.n_dict.get(k) != None:
            self.n_dict[k].itemPath()
