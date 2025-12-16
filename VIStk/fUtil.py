from tkinter import *
from tkinter.font import Font as tkfont
import sys

global cfp
if str.upper(sys.platform)=="WIN32":
    cfp = 'win'
else:
    cfp = 'rasp'

class fUtil():
    def __init__(self):
        if cfp == 'win':
            self.defont = "Arial"
        else: #Liberation Sans is the Linux Available version of Arial
            self.defont = "LiberationSans"

    def mkfont(size:int,bold:bool=False,font:str="default"):
        """Creates a font string with wom fonts"""

        if font == "default":
            return f"{fUtil().defont} {size}{' bold' if bold is True else ''}"
        
    def autosize(e:Event=None, relations:list[Widget]=None, offset:int=None,shrink:int=0):
        """Automatically sizes text given a widget with text."""
        if not e is None: #Always need an event
            #Get info from widget
            widget:Widget = e.widget
            w = widget.winfo_width() - 1 - shrink
            h = widget.winfo_height() - 1
            if w < 1 or h < 1:
                return None
            _root=widget.winfo_toplevel()
            ffont = tkfont(_root, widget["font"])
            fw = ffont.measure(widget["text"])
            fh = ffont.metrics('linespace')

            #Check widget with tightest relation
            if not relations is None:
                tempwi = widget
                for wi in relations:
                    if isinstance(wi["text"],str):
                        if wi.winfo_width() > 1:
                            test = (wi.winfo_width() - 1 - ffont.measure(wi["text"]) < w-fw)
                        else:
                            test = False
                    else: test = False
                    if test:
                        widget = wi
                    else:
                        if wi.winfo_height() - 1 < h:#text has same height so only widget height must be smaller
                            if wi.winfo_height() > 1:
                                widget = wi
                    w = widget.winfo_width() - 1 - shrink
                    h = widget.winfo_height() - 1
                    fw = ffont.measure(widget["text"])
                relations.append(tempwi)

            #Final Control Sizes
            _family = ffont.actual(option="family").replace(" ", "")
            _size = ffont.actual(option="size")
            _weight = ffont.actual(option="weight")

            while True: #Make text larger than frame
                if fw < w and fh < h:
                    _size = _size + 1
                else:
                    break
                ffont = tkfont(widget.winfo_toplevel(), f"{_family} {_size} {_weight}")
                fh = ffont.metrics('linespace')
                fw = ffont.measure(widget["text"])

            while True: #Make text fit in frame
                if fw <= w and fh <= h:
                    break
                else:
                    if _size == 0:break
                    _size = _size - 1
                ffont = tkfont(_root, f"{_family} {_size} {_weight}")
                fh = ffont.metrics('linespace')
                fw = ffont.measure(widget["text"])

            if not offset is None: #Apply offset
                _size = _size - offset

            if not relations is None: #Correct relations
                for wi in relations:
                    wi.configure(font = f"{_family} {_size} {_weight}")
            else:
                widget.configure(font = f"{_family} {_size} {_weight}")
