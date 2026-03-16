from tkinter import *
from tkinter import ttk
from VIStk.Objects import Root
import sys

root = Root()
root.title('New VIS Project')

frame = Frame(root)
frame.pack(fill="both", expand=True)

def do_focus(event=None):
    x,y = root.winfo_pointerxy()
    root.winfo_containing(x,y).focus()

root.bind("<1>", do_focus)