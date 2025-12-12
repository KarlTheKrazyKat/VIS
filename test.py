from tkinter import *
from VIS.Objects import *
from VIS.Widgets import *
import time

root = Root()
root.WindowGeometry.setGeometry(width=40,height=40,align="center",size_style="screen_relative")

def subWindow():
    subroot = MenuWindow(root,"test.json")

vb_test = Button(root, text="Open Submenu", command=subWindow)
vb_test.grid(row=1,column=1,sticky=(N, S, E, W))

root.mainloop()