from typing import Literal
from tkinter import *
from tkinter import ttk
from VIStk.Objects import SubRoot

class QuestionWindow(SubRoot):
    """An empty popout window"""
    def __init__(self, question:str|list[str], answer:str, parent:Toplevel|Tk, ycommand=None, droplist:list=None, *args,**kwargs):
        """Will create a question window
            y = yes
            n = no
            r = return
            u = continue
            b = back
            x = close
            c = confirm
            d = dropdown
        """
        super().__init__(*args,**kwargs)
        cs = len(list(answer))

        for i in range(0,cs,1):
            self.columnconfigure(i,weight=1)

        #Resolve Question
        if isinstance(question, str):
            self.rowconfigure(0, weight=1)
            rs = 1
            Label(self, text=question, anchor="w").grid(row=0,column=0,columnspan=cs,sticky=(N,S,E,W))
        else:
            rs = len(question)
            for i in range(0,rs,1):
                self.rowconfigure(i, weight=1)
                Label(self, text=question[i], anchor="w").grid(row=i,column=0,columnspan=cs,sticky=(N,S,E,W))
        self.rowconfigure(rs, weight=1)

        #Resolve Answer
        self.elements = list(answer)

        self.screen_elements = []
        for i in range(0,len(self.elements),1):
            match self.elements[i]:
                case "y":
                    self.screen_elements.append(Button(self, text="Yes", command = lambda: self.ycom(ycommand)))
                    self.screen_elements[i].grid(row=rs,column=i,sticky=(N,S,E,W))
                case "n":
                    self.screen_elements.append(Button(self, text="No", command = self.xcom))
                    self.screen_elements[i].grid(row=rs,column=i,sticky=(N,S,E,W))
                case "r":
                    self.screen_elements.append(Button(self, text="Return", command = self.xcom))
                    self.screen_elements[i].grid(row=rs,column=i,sticky=(N,S,E,W))
                case "u":
                    self.screen_elements.append(Button(self, text="Continue", command = lambda: self.ycom(ycommand)))
                    self.screen_elements[i].grid(row=rs,column=i,sticky=(N,S,E,W))
                case "b":
                    self.screen_elements.append(Button(self, text="Back", command = self.xcom))
                    self.screen_elements[i].grid(row=rs,column=i,sticky=(N,S,E,W))
                case "x":
                    self.screen_elements.append(Button(self, text="Close", command = self.xcom))
                    self.screen_elements[i].grid(row=rs,column=i,sticky=(N,S,E,W))
                case "c":
                    self.screen_elements.append(Button(self, text="Confirm", command = lambda: self.ycom(ycommand)))
                    self.screen_elements[i].grid(row=rs,column=i,sticky=(N,S,E,W))
                case "d":
                    self.screen_elements.append(ttk.Combobox(self, values=droplist))
                    self.screen_elements[i].grid(row=rs,column=i,sticky=(N,S,E,W))
                case _:
                    pass


        #Ensure visibility
        self.focus_force()
        
        #SubWindow Geometry
        self.update()
        self.WindowGeometry.getGeometry(True)
        self.WindowGeometry.setGeometry(width=self.winfo_width(),
                                        height=self.winfo_height(),
                                        align="center",
                                        size_style="window_relative",
                                        window_ref=parent)

    def ycom(self,command):
        self.destroy()
        if not command is None:
            command()

    def xcom(self):
        self.destroy()