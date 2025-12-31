import shutil
from zipfile import *
from VIStk.Objects import Root
from tkinter import ttk
from tkinter import filedialog
from tkinter import *
from PIL import Image
import PIL.ImageTk
import sys
import json
import os
import subprocess

#%Plans and Modifications
#should have the option to create desktop shortcuts to program

#%Installer Code
#Load .VIS project info
root_location = "/".join(__file__.replace("\\","/").split("/")[:-1])

archive = ZipFile(root_location+'/binaries.zip','r')#Should find file differently
pfile = archive.open(".VIS/project.json")
info = json.load(pfile)
pfile.close()

title = list(info.keys())[0]

#%Locate Binaries
installables = []
for i in archive.namelist():
    if not any(breaker in i for breaker in ["Icons/","Images/",".VIS/","_internal"]):
        if "." in i: #Remove Extension
            installables.append(".".join(i.split(".")[:-1]))
        else: #Sometimes No Extension
            installables.append(i)

#%Configure Root
root = Root()

#Root Title
root.title(title + " Installer")

#Root Icon
icon_file = info[title]["defaults"]["icon"]
if sys.platform == "win32":
    icon_file = icon_file + ".ico"
else:
    icon_file = icon_file + ".xbm"

i_file = archive.open("Icons/"+icon_file)
d_icon = Image.open(i_file)
icon = PIL.ImageTk.PhotoImage(d_icon)
i_file.close()
root.iconphoto(False, icon)

#Root Geometry
root.WindowGeometry.setGeometry(width=360,height=200,align="center")
root.minsize(width=360,height=200)

#Root Layout
root.rowconfigure(1,weight=1,minsize=120)
root.rowconfigure(2,weight=1,minsize=40)
root.rowconfigure(3,weight=1,minsize=40)

root.columnconfigure(1,weight=1,minsize=180)
root.columnconfigure(2,weight=1,minsize=180)

#Scrollable frame for selection
install_frame = ttk.Frame(root,)
canvas = Canvas(install_frame,height=install_frame.winfo_height(),width=install_frame.winfo_width())
scrollbar = ttk.Scrollbar(install_frame, orient="vertical", command=canvas.yview)
install_options = ttk.Frame(canvas,height=root.winfo_height(),width=root.winfo_width())

canvas.create_window((0, 0), window=install_options, anchor="nw")

install_options.bind(
    "<Configure>",
    lambda e: canvas.configure(
        scrollregion=canvas.bbox("all")
    )
)
canvas.configure(yscrollcommand=scrollbar.set)

canvas.pack(side="left", fill="both", expand=True)
scrollbar.pack(side="right", fill="y")

install_frame.grid(row=1,column=1,columnspan=2,sticky=(N,S,E,W))

install_options.rowconfigure(0,weight=1)

install_options.columnconfigure(1,minsize=15,weight=1)
install_options.columnconfigure(2,weight=1)

#Create Checkbutton Elements
all_options = []
var_options = []
img_options = []

var_all = IntVar()

def all_state():
    """Sets the state of all the check boxes"""
    for i in var_options:
        i.set(var_all.get())

all = ttk.Checkbutton(install_options,
                      text="All",
                      variable=var_all,
                      command=all_state)
all.grid(row=0,column=1,columnspan=2,sticky=(N,S,E,W))
all.state(['!alternate'])

def is_all():
    """Checks if all of the states are selected"""
    for i in all_options:
        if var_options[all_options.index(i)].get() == 0:
            var_all.set(0)
            break
    else:
        var_all.set(1)

#Create Checkboxes
for i in installables:
    if i == "": continue
    #Configure Row
    install_options.rowconfigure(installables.index(i)+1,weight=1)

    #Resolve Installable Icon
    if info[title]["Screens"][i].get("icon") is None:
        img_options.append(PIL.ImageTk.PhotoImage(d_icon.resize((16,16))))

    else:
        icon_file = info[title]["Screens"][i]["icon"]
        if sys.platform == "win32":
            icon_file = icon_file + ".ico"
        else:
            icon_file = icon_file + ".xbm"
        
        img_options.append(PIL.ImageTk.PhotoImage(Image.open(archive.open("Icons/"+icon_file)).resize((16,16))))
        i_file.close()
    #Create Checkbox in List
    var_options.append(IntVar())
    all_options.append(ttk.Checkbutton(install_options,
                                       text=i,
                                       variable=var_options[-1],
                                       command=is_all,
                                       image=img_options[-1],
                                       compound=LEFT))
    all_options[-1].grid(row=installables.index(i)+1,column=2,sticky=(N,S,E,W))
    all_options[-1].state(['!alternate'])

#File Location
file_location = StringVar()
if sys.platform in ["win32","linux"]:
    if sys.platform=="win32":
       file_location.set("C:/Program Files")
    else:
        file_location.set(os.path.expanduser("~user"))

fframe = ttk.Frame(root)
fframe.grid(row=2,column=1,columnspan=2,sticky=(N,S,E,W))

fframe.rowconfigure(1, weight=1)
fframe.columnconfigure(1,weight=1,minsize=250)
fframe.columnconfigure(2,weight=1,minsize=110)

file = ttk.Label(fframe,textvariable=file_location,relief="sunken")
file.grid(row=1,column=1,padx=2,pady=8,sticky=(N,S,E,W))

def select():
    """Select the file location"""
    selection = filedialog.askdirectory(initialdir=file_location.get(), title="Select Installation Directory")
    if not selection in ["", None]:
        file_location.set(selection)

#File Location Selection
fs = ttk.Button(fframe,
                text="Select Directory",
                command=select)
fs.grid(row=1,column=2,padx=2,pady=4,sticky=(N,S,E,W))

#Frame to beautify the controls
control = ttk.Frame(root)
control.grid(row=3,column=2,sticky=(N,S,E,W))

control.rowconfigure(1,weight=1)
control.columnconfigure(1,weight=1)
control.columnconfigure(2,weight=1)

#Close Button
close = ttk.Button(control,text="Close",command=root.destroy)
close.grid(row=1,column=1,padx=2,pady=4,sticky=(N,S,E,W))

def binstall():
    """Installs the selected binaries"""
    some=False
    for i in range(0,len(var_options),1):
        if var_options[i].get() == 1:
            some = True
            break
    if some:

        close.state(["disabled"])
        fs.state(["disabled"])
        install_options.unbind("<Configure>")
        install_options.destroy()
        
        #scrollbar.destroy()
        root.update()

        location = file_location.get()+"/"+title
        if os.path.exists(location):
            shutil.rmtree(location)
        os.mkdir(location)

        if var_all.get() == 1:
            canvas.create_text(10,10,text="Installing All...",anchor="nw")
            root.update()
            canvas.delete("all")
            archive.extractall(location)

            for i in range(0,len(installables),1):
                for file in archive.namelist():
                    if file.startswith(installables[i]):
                        if sys.platform == "linux":
                            subprocess.call(f"sudo chmod +x {location}/{file}", shell=True)
        else:
            os.mkdir(location+"/.VIS")
            os.mkdir(location+"/Images")
            os.mkdir(location+"/Icons")
            os.mkdir(location+"/_internal")
            for file in archive.namelist():
                canvas.delete("all")
                canvas.create_text(10,10,text=f"Installing {file}...",anchor="nw")
                root.update()
                if file.startswith(".VIS/"):
                    archive.extract(file, location)
                
                canvas.delete("all")
                canvas.create_text(10,10,text=f"Installing {file}...",anchor="nw")
                root.update()
                if file.startswith("Images/"):
                    archive.extract(file, location)

                canvas.delete("all")
                canvas.create_text(10,10,text=f"Installing {file}...",anchor="nw")
                root.update()
                if file.startswith("Icons/"):
                    archive.extract(file, location)

                canvas.delete("all")
                canvas.create_text(10,10,text=f"Installing {file}...",anchor="nw")
                root.update()
                if file.startswith("_internal/"):
                    archive.extract(file, location)

            for i in range(0,len(var_options),1):
                if var_options[i].get() == 1:
                    for file in archive.namelist():
                        if file.startswith(installables[i]):
                            canvas.delete("all")
                            canvas.create_text(10,10,text=f"Installing {file}...",anchor="nw")
                            root.update()
                            archive.extract(file, location)
                            if sys.platform == "linux":
                                subprocess.call(f"sudo chmod +x {location}/{file}", shell=True)

        root.destroy()

#Install Button
install = ttk.Button(control, text="Install",command=binstall)
install.grid(row=1,column=2,padx=2,pady=4,sticky=(N,S,E,W))

root.mainloop()