from tkinter import *
from VIStk.Objects import *
from VIStk.Widgets import *
import time

root = Root()
root.WindowGeometry.setGeometry(width=40,height=40,align="center",size_style="screen_relative")

def warnWindow():
    newroot = WarningWindow(parent=root,
                             warning="Warning: Something!!!",
                            )

def subWindow():
    subroot = QuestionWindow(parent=root,
                             question=["Some info...",
                                       "Additional information given",
                                       "Do you want to continue"],
                             answer = "xu",
                             ycommand=warnWindow
                            ).fullscreen()

vb_test = Button(root, text="Open Submenu", command=subWindow)
vb_test.grid(row=1,column=1,sticky=(N, S, E, W))

root.mainloop()