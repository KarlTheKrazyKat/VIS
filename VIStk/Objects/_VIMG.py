from tkinter import *
from PIL import Image
import PIL.ImageTk
from PIL.Image import Resampling
from VIStk.Structures._Project import Project
import os
import glob

class VIMG():
    def __init__(self,  holder:Widget, path:str, absolute_path:bool=False, size:tuple[int,int]|list[int,int]=None, fill:Widget=None):
        self.holder = holder
        """The `Widget` to size the `Image` to in"""
        
        if absolute_path is True:
            self.path = path
        else:
            pimdir = Project().p_images + "/"
            self.path = pimdir + path
            if not os.path.exists(self.path):
                self.path = pimdir + glob.glob(path+"*",root_dir=pimdir)[0]

        self.Image = Image.open(self.path)
        
        if size is None:
            self.width = self.Image.width
            self.height = self.Image.height
        else:
            self.width = size[0]
            self.height = size[1]

        self.fill = fill
        if not self.fill is None:
            holder.bind("<Configure>", self.resize)

    def resize(self, e=None):
        """Resizes an image to the size of its parent frame"""
        img = Image.open(self.path)
        f_w = self.fill.winfo_width()
        f_h = self.fill.winfo_height()
        f_r = f_h/f_w

        i_w = img.width
        i_h = img.height
        i_r = i_h/i_w

        if f_r>i_r:
            n_w=f_w
            n_h=int(n_w*i_r)
        else:
            n_h=f_h
            n_w=int(n_h/i_r)

        img = img.resize((n_w,n_h),resample=Resampling.BICUBIC)

        imag = PIL.ImageTk.PhotoImage(img)

        self.holder.image = imag
        self.holder.configure(image=imag)