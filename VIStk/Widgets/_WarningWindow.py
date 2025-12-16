from VIStk.Widgets._QuestionWindow import QuestionWindow
from tkinter import *

class WarningWindow(QuestionWindow):
    def __init__(self, warning:str|list[str], parent:Toplevel|Tk, *args, **kwargs):
        super().__init__(question=warning, parent=parent, answer="u", ycommand=None, *args, **kwargs)
        self.screen_elements[0]["anchor"] = "center"
        self.focus_force()
        self.transient(parent)
        self.grab_set()
        parent.wait_window(self)