from tkinter import *
from VIS.Objects import *
import time

root = Root()
for i in range(1,101,1):
    root.WindowGeometry.setGeometry(width=i,height=i,align="nw",size_style="screen_relative")
    root.update()
    time.sleep(0.1)
root.mainloop()