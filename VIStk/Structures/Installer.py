import shutil
from zipfile import ZipFile
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
import platformdirs
if sys.platform == "win32": import winshell
from pathlib import Path

QUIET = False
cinstalls = []
dinstalls = []

if len(sys.argv) > 1:
    if (sys.argv[0] == sys.argv[1]):
        pargs = sys.argv[1:]
    else:
        pargs = sys.argv

    pargs = " ".join(pargs)
    pargs = pargs.split("--")
    for i in pargs:
        sargs = i.split(" ")
        flag = sargs[0]
        args = sargs[1:]

        if flag in ["Quiet", "quiet", "Q", "q"]:
            QUIET = True
            for a in args:
                cinstalls.append(a)

        if flag in ["Desktop", "desktop", "D", "d"]:
            for a in args:
                dinstalls.append(a)


#%Plans and Modifications
#should have the option to create desktop shortcuts to program

#%Installer Code
#Load .VIS project info
root_location = Path("/".join(__file__.replace("\\","/").split("/")[:-1]))

archive = ZipFile(os.path.join(root_location,'binaries.zip'),'r')#Should find file differently
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

#%Core Install & Shorcut Creation
def shortcut(name:str, location:Path):
    """Make shortcut for arguments"""
    if sys.platform == "win32":
        winshell.CreateShortcut(
            Path=(os.path.join(winshell.desktop(), f"{name}.lnk")),
            Target=os.path.join(location, f"{name}.exe"),
            StartIn=f"{location}"
        )
    else:
        icon = info[title]["Screens"][name].get("icon")
        if icon is None:
            icon = info[title]["defaults"]["icon"]
        icon = os.path.join(location,"Icons",icon+".ico")
        binary = os.path.join(location,name)
        lines=[]
        lines.append("[Desktop Entry]\n")
        lines.append(f"Name={name}\n")
        lines.append(f"Icon={icon}\n")
        lines.append(f"Exec={binary}\n")
        lines.append(f"Type=Application\n")
        lines.append(f"Categories=Application;\n")
        lines.append(f"Name[en_GB]={name}\n")
        lines.append(f"Terminal=false\n")
        lines.append(f"StartupNotify=true\n")
        lines.append(f"Path={location}")

        with open(os.path.join(platformdirs.user_desktop_path(),name+".desktop"),"w") as f:
            f.writelines(lines)

        subprocess.call(f"chmod +x {os.path.join(platformdirs.user_desktop_dir(),i+'.desktop')}", shell=True)

def extal(file, location):
    """Extracts file to the location"""
    archive.extract(file, location)
    if sys.platform == "linux":
        subprocess.call(f"chmod +x {os.path.join(location,file)}", shell=True)

def adjacents(location):
    """Installs adjacent files from .VIS, Images, Icons, _internal"""
    if not os.path.exists(location):
        #shutil.rmtree(location)
        os.mkdir(location)

    if not os.path.exists(os.path.join(location,".VIS")):
        os.mkdir(os.path.join(location,".VIS"))

    if not os.path.exists(os.path.join(location,"Images")):
        os.mkdir(os.path.join(location,"Images"))

    if not os.path.exists(os.path.join(location,"Icons")):
        os.mkdir(os.path.join(location,"Icons"))

    if not os.path.exists(os.path.join(location,"_internal")):
        os.mkdir(os.path.join(location,"_internal"))

#%Install & Escape Command Line Args
if QUIET is True:
    floc = str(platformdirs.user_config_path(appauthor=info[title]["metadata"].get("company"),appname=title))
    if floc.endswith(f"/{title}") or floc.endswith(f"\\{title}"):
        location = Path(floc)
    else:
        location = Path(floc,title)

    for i in cinstalls:
        for file in archive.namelist():
            if file.startswith(i):
                extal(file, location)
    
    for i in dinstalls:
        shortcut(i, location)

    sys.exit()

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
root.WindowGeometry.setGeometry(width=720,height=360,align="center")
root.minsize(width=720,height=360)

#Root Layout
root.rowconfigure(0,weight=1,minsize=30)
root.rowconfigure(1,weight=1,minsize=250)
root.rowconfigure(2,weight=1,minsize=30)
root.rowconfigure(3,weight=1,minsize=30)

root.columnconfigure(1,weight=1,minsize=360)
root.columnconfigure(2,weight=1,minsize=360)

#Selection Header
header = ttk.Label(root, text="Select Installables")
header.grid(row=0,column=1,columnspan=2,sticky=(N,S,E,W))

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


def is_all():
    """Checks if all of the states are selected"""
    for i in all_options:
        if var_options[all_options.index(i)].get() == 0:
            var_all.set(0)
            break
    else:
        var_all.set(1)

#Create Checkboxes
def makechecks(source:list[str]):
    """Makes checkboxes for the given selections"""
    global all_options, var_options, img_options, var_all
    all_options = []
    var_options = []
    img_options = []

    var_all = IntVar()

    all = ttk.Checkbutton(install_options,
                        text="All",
                        variable=var_all,
                        command=all_state)
    all.grid(row=0,column=1,columnspan=2,sticky=(N,S,E,W))
    all.state(['!alternate'])

    for i in source:
        if i == "": continue
        #Configure Row
        install_options.rowconfigure(source.index(i)+1,weight=1)

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
        all_options[-1].grid(row=source.index(i)+1,column=2,sticky=(N,S,E,W))
        all_options[-1].state(['!alternate'])

makechecks(installables)

#File Location
file_location = StringVar()

file_location.set(platformdirs.user_config_path(appauthor=info[title]["metadata"].get("company"),appname=title))


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
control.grid(row=3,column=1,columnspan=2,sticky=(N,S,E,W))

control.rowconfigure(1,weight=1)
control.columnconfigure(0,weight=1)
control.columnconfigure(1,weight=1)
control.columnconfigure(2,weight=1)

def previous():
    next = ttk.Button(control,text="Next",command=nextpage)
    next.grid(row=1,column=2,padx=2,pady=4,sticky=(N,S,E,W))

    for i in install_options.winfo_children():
        i.destroy()

    header["text"] = "Select Installables"
    makechecks(installables)

#Back Button
back = ttk.Button(control, text="Back", command=previous)
back.grid(row=1,column=1,padx=2,pady=4,sticky=(N,S,E,W))

#Close Button
close = ttk.Button(control,text="Close",command=root.destroy)
close.grid(row=1,column=0,padx=2,pady=4,sticky=(N,S,E,W))

def binstall(desktop:list[str]):
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

        if file_location.get().endswith(f"/{title}") or file_location.get().endswith(f"\\{title}"):
            location = Path(file_location.get())
        else:
            location = Path(file_location.get(),title)

        adjacents(location)#Install adjacent files

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

        for i in desktop:
            for file in archive.namelist():
                if file.startswith(i):
                    canvas.delete("all")
                    canvas.create_text(10,10,text=f"Installing {file}...",anchor="nw")
                    root.update()
                    extal(file,location)
        
        for i in desktop:
            if var_options[desktop.index(i)].get() == 1:
                canvas.delete("all")
                canvas.create_text(10,10,text=f"Creating Desktop Shortcut for {file}...",anchor="nw")
                root.update()
                shortcut(i, location)

        root.destroy()

def nextpage():
    """Goes to the next installer page"""
    next.destroy()

    for i in install_options.winfo_children():
        i.destroy()

    desktop = []
    for i in range(0,len(var_options),1):
        if var_options[i].get() == 1:
            desktop.append(installables[i])

    header["text"] = "Select Desktop Shortcuts"
    makechecks(desktop)

    #Install Button
    install = ttk.Button(control, text="Install",command=lambda: binstall(desktop))
    install.grid(row=1,column=2,padx=2,pady=4,sticky=(N,S,E,W))

next = ttk.Button(control,text="Next",command=nextpage)
next.grid(row=1,column=2,padx=2,pady=4,sticky=(N,S,E,W))

root.mainloop()