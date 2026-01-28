from tkinter import *
from VIStk.Objects._Layout import Layout

class LayoutFrame(Frame):
    """A Frame with an inherent Layout SubObject"""
    def __init__(self, master, *args, **kwargs):
        """Creates a Frame and attaches a Layout"""
        super().__init__(master=master, *args, **kwargs)
        self.Layout = Layout(self)
