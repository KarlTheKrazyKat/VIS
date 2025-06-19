import json
from tkinter import *
from tkinter import ttk
import subprocess
import sys
import os

if str.upper(sys.platform)=="WIN32":
    cfp = 'win'
else:
    cfp = 'rasp'

class Item(Menu):
    """Each item in the menu is created from the corresponding .json file. Each path should be given relative to xyz/WOM/
    """
    def __init__(self,root,_root,path,nav,*args,**kwargs):
        self.button = ttk.Button(root, *args, **kwargs)
        self.root = root
        self.path = path
        self._root = _root
        self.nav = nav
        self.button.config(command = self.itemPath)
        #self.button.pack()

    def itemPath(self):
        self.root.destroy()
        if ".exe" in self.path:
            os.startfile(self.path)
        else:
            subprocess.call("pythonw.exe "+self.path)
        self._root.destroy()
            
    

class Menu:
    """The menu class drawings a column of buttons with subprocess calls to paths defined in a corresponding .json file.

    Has two roots because can destory both main window and subwindow on redirect.
    """
    def __init__(self, root, _root, path):
        root.focus_force()#use to force window into focus
        self.path = path
        self.n_dict = {}
        with open(path) as file:
            self.dict = json.load(file)


        for item in self.dict:

            ob = Item(root,_root,
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

            
        