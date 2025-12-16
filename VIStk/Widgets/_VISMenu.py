import json
from tkinter import *
from tkinter import ttk
from VIStk.Widgets import MenuItem

class VISMenu():
    """The menu class drawings a column of buttons with subprocess calls to paths defined in a corresponding .json file.

    Has two roots because can destory both main window and subwindow on redirect.
    """
    def __init__(self, parent:Frame|LabelFrame|Toplevel|Tk, path:str):
        """
        Args:
            root (Tk): Master root for destruction on redirect
            _root (Toplevel): Toplevel object to create menu on
            path (str): Path to .json file describing menu
            destroyOnRedirect (bool): If True the root window will be destroyed on redicet
        """

        self.parent = parent
        self.root = self.parent.winfo_toplevel()
        self.path = path
        self.ob_dict = []
        self.n_dict = {}

        #Open json file for menu structure
        with open(path) as file:
            self.dict:dict = json.load(file)
        self.parent.grid_columnconfigure(0,weight=1)
        for i in range(0, len(self.dict.keys()), 1):
            self.parent.grid_rowconfigure(i,weight=1)

        x = 0
        for item in self.dict:
            ob = MenuItem(self.parent,
                      path= self.dict[item]["path"],
                      nav = self.dict[item]["nav"],
                      text = self.dict[item]["text"],
                      relief="flat"
                      )
            ob.button.grid(row=x, column=0, sticky=(N,S,E,W))
            self.ob_dict.append(ob)
            self.n_dict[ob.nav]=ob
            x += 1

        self.root.bind("<KeyPress>",self.menuNav)
    
    def menuNav(self,happ:Event):
        k=happ.char
        if self.n_dict.get(k) != None:
            self.n_dict[k].itemPath()
