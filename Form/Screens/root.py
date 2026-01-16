from tkinter import *
from VIStk.Objects import Root
from VIStk.Structures.project import Project

root = Root()
project = Project()

def do_focus(event=None):
    x,y = root.winfo_pointerxy()
    root.winfo_containing(x,y).focus()

root.bind("<1>", do_focus)