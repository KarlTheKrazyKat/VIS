from zipfile import ZipFile
from VIStk.Objects import Root
from VIStk.Objects._ArgHandler import ArgHandler
import tkinter as tk
from tkinter import ttk
from tkinter import filedialog
from PIL import Image
import PIL.ImageTk
import sys
import json
import os
import subprocess
import datetime
import platformdirs
if sys.platform == "win32": import winshell
from pathlib import Path

QUIET = False
cinstalls = []
dinstalls = []
custom_path = None

def _on_quiet(args):
    global QUIET
    QUIET = True
    for a in args:
        if a: cinstalls.append(a)

def _on_desktop(args):
    for a in args:
        if a: dinstalls.append(a)

def _on_path(args):
    global custom_path
    if args:
        custom_path = " ".join(args)

def _on_help(args):
    print("Usage: Installer.exe [--Quiet [screens...]] [--Desktop <screens...>] [--Path <dir>] [--Help]")
    print()
    print("Flags:")
    print("  --Quiet   [s1] [s2] ...  Install silently (no GUI); installs all screens if none listed")
    print("  --Desktop <s1> <s2> ...  Create desktop shortcuts for listed screens (requires --Quiet)")
    print("  --Path    <directory>    Override the install location (requires --Quiet)")
    print("  --Help                   Show this message and exit")
    print()
    print("If no flags are given, the GUI installer will launch.")
    sys.exit(0)

handler = ArgHandler()
handler.newFlag("Quiet", _on_quiet)
handler.newFlag("Desktop", _on_desktop)
handler.newFlag("Path", _on_path)
handler.newFlag("Help", _on_help)
handler.handle(sys.argv)

# Enforce --Quiet requirement for --Desktop and --Path
if not QUIET and (dinstalls or custom_path):
    print("Warning: --Desktop and --Path require --Quiet. Ignoring these flags.")
    print("Launching GUI installer...")
    dinstalls.clear()
    custom_path = None


#%Plans and Modifications
#should have the option to create desktop shortcuts to program

#%Installer Code
#Load .VIS project info
#Try self-contained mode: binaries.zip appended to the executable itself
archive = None
if getattr(sys, 'frozen', False):
    try:
        test = ZipFile(sys.executable, 'r')
        test.open(".VIS/project.json").close()
        test.close()
        archive = ZipFile(sys.executable, 'r')
    except Exception:
        pass

#Fall back to external binaries.zip
if archive is None:
    root_location = Path(__file__).parent
    archive_path = os.path.join(root_location, 'binaries.zip')
    if not os.path.exists(archive_path):
        print(f"Error: Could not find binaries.zip")
        print("The installer archive is missing or was not bundled correctly.")
        sys.exit(1)
    archive = ZipFile(archive_path, 'r')
pfile = archive.open(".VIS/project.json")
info = json.load(pfile)
pfile.close()

title = list(info.keys())[0]
app_version = info[title].get("metadata", {}).get("version", "unknown")

#%Locate Binaries
installables = []
for i in archive.namelist():
    if not any(breaker in i for breaker in ["Icons/","Images/",".VIS/","_internal/"]):
        if "." in i: #Remove Extension
            name = ".".join(i.split(".")[:-1])
        else: #Sometimes No Extension
            name = i
        if name and name not in installables:
            installables.append(name)

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

        subprocess.call(f"chmod +x {os.path.join(platformdirs.user_desktop_path(),name+'.desktop')}", shell=True)

def extal(file, location):
    """Extracts file to the location. Only chmod binaries on Linux."""
    archive.extract(file, location)
    if sys.platform == "linux":
        # Only chmod files that are actual binaries (no extension or .sh)
        basename = os.path.basename(file)
        if "." not in basename or basename.endswith(".sh"):
            subprocess.call(f"chmod +x {os.path.join(location,file)}", shell=True)

def adjacents(location):
    """Installs adjacent files from .VIS, Images, Icons, _internal"""
    os.makedirs(os.path.join(location, ".VIS"), exist_ok=True)
    os.makedirs(os.path.join(location, "Images"), exist_ok=True)
    os.makedirs(os.path.join(location, "Icons"), exist_ok=True)
    os.makedirs(os.path.join(location, "_internal"), exist_ok=True)


def write_install_log(location, selected_screens, desktop_shortcuts):
    """Write install_log.json recording what was installed."""
    # Collect _internal/ subdirectories (immediate children only)
    internal_dir = os.path.join(location, "_internal")
    directories = [".VIS", "Icons", "Images", "_internal"]
    if os.path.isdir(internal_dir):
        for entry in os.listdir(internal_dir):
            if os.path.isdir(os.path.join(internal_dir, entry)):
                directories.append(f"_internal/{entry}")

    # Build screen list with versions
    screens = []
    for name in selected_screens:
        scr_info = info[title]["Screens"].get(name, {})
        ext = ".exe" if sys.platform == "win32" else ""
        screens.append({
            "name": name,
            "version": scr_info.get("version", ""),
            "executable": name + ext,
        })

    registry_key = ""
    if sys.platform == "win32":
        registry_key = f"HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\{title}"

    log = {
        "app_name": title,
        "app_version": app_version,
        "install_date": datetime.datetime.now().isoformat(timespec="seconds"),
        "install_location": str(location),
        "company": info[title].get("metadata", {}).get("company", ""),
        "screens": screens,
        "desktop_shortcuts": list(desktop_shortcuts),
        "directories": directories,
        "registry_key": registry_key,
    }

    log_path = os.path.join(location, "install_log.json")
    with open(log_path, "w") as f:
        json.dump(log, f, indent=2)


def register_uninstall(location):
    """Register the application in Windows Add/Remove Programs."""
    if sys.platform != "win32":
        return
    try:
        import winreg
        key_path = f"Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\{title}"
        uninstaller = os.path.join(location, "Uninstaller.exe")

        # Estimate installed size in KB
        total_kb = 0
        for dirpath, dirnames, filenames in os.walk(str(location)):
            for fn in filenames:
                try:
                    total_kb += os.path.getsize(os.path.join(dirpath, fn))
                except OSError:
                    pass
        total_kb = total_kb // 1024

        icon_name = info[title]["defaults"].get("icon", "VIS")
        icon_path = os.path.join(location, "Icons", icon_name + ".ico")

        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, key_path, 0,
                                winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, "DisplayName", 0, winreg.REG_SZ, title)
            winreg.SetValueEx(key, "UninstallString", 0, winreg.REG_SZ,
                              f'"{uninstaller}"')
            winreg.SetValueEx(key, "InstallLocation", 0, winreg.REG_SZ,
                              str(location))
            winreg.SetValueEx(key, "DisplayVersion", 0, winreg.REG_SZ,
                              app_version)
            company = info[title].get("metadata", {}).get("company", "")
            if company:
                winreg.SetValueEx(key, "Publisher", 0, winreg.REG_SZ, company)
            if os.path.exists(icon_path):
                winreg.SetValueEx(key, "DisplayIcon", 0, winreg.REG_SZ,
                                  icon_path)
            winreg.SetValueEx(key, "EstimatedSize", 0, winreg.REG_DWORD,
                              total_kb)
            winreg.SetValueEx(key, "NoModify", 0, winreg.REG_DWORD, 1)
            winreg.SetValueEx(key, "NoRepair", 0, winreg.REG_DWORD, 1)
    except Exception:
        pass


#%Install & Escape Command Line Args
if QUIET is True:
    if custom_path:
        floc = custom_path
    else:
        floc = str(platformdirs.user_config_path(appauthor=info[title]["metadata"].get("company"),appname=title))
    if floc.endswith(f"/{title}") or floc.endswith(f"\\{title}"):
        location = Path(floc)
    else:
        location = Path(floc,title)

    # Default to all screens if none specified
    if not cinstalls:
        cinstalls = list(installables)
        print(f"No screens specified — installing all {len(cinstalls)} screen(s).")

    print(f"Installing {title} v{app_version} to {location}")
    adjacents(location)

    for i in cinstalls:
        matched = False
        for file in archive.namelist():
            if file == i or file.startswith(i + ".") or file.startswith(i + "/"):
                print(f"  Extracting {file}")
                extal(file, location)
                matched = True
        if not matched:
            print(f"  Warning: no archive entry matches '{i}'")

    for i in dinstalls:
        print(f"  Creating shortcut: {i}")
        shortcut(i, location)

    write_install_log(location, cinstalls, dinstalls)
    register_uninstall(location)
    print("Installation complete.")
    archive.close()
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
header_frame = ttk.Frame(root)
header_frame.grid(row=0,column=1,columnspan=2,sticky=(tk.N,tk.S,tk.E,tk.W))
header_frame.columnconfigure(0, weight=1)
header_frame.columnconfigure(1, weight=0)
header = ttk.Label(header_frame, text="Select Installables")
header.grid(row=0, column=0, sticky=(tk.W,), padx=(4, 0))
version_label = ttk.Label(header_frame, text=f"v{app_version}")
version_label.grid(row=0, column=1, sticky=(tk.E,), padx=(0, 8))

#Scrollable frame for selection
install_frame = ttk.Frame(root)
canvas = tk.Canvas(install_frame,height=install_frame.winfo_height(),width=install_frame.winfo_width())
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

install_frame.grid(row=1,column=1,columnspan=2,sticky=(tk.N,tk.S,tk.E,tk.W))

install_options.rowconfigure(0,weight=1)

install_options.columnconfigure(1,minsize=15,weight=0)
install_options.columnconfigure(2,weight=1)
install_options.columnconfigure(3,weight=0,minsize=60)

#Create Checkbutton Elements
all_options = []
var_options = []
img_options = []

var_all = tk.IntVar()

def all_state():
    """Sets the state of all the check boxes"""
    for v in var_options:
        v.set(var_all.get())


def is_all():
    """Checks if all of the states are selected"""
    for v in var_options:
        if v.get() == 0:
            var_all.set(0)
            break
    else:
        var_all.set(1)

#Create Checkboxes
def makechecks(source:list[str], show_versions:bool=True):
    """Makes checkboxes for the given selections"""
    global all_options, var_options, img_options, var_all
    all_options = []
    var_options = []
    img_options = []

    var_all = tk.IntVar()

    select_all = ttk.Checkbutton(install_options,
                        text="All",
                        variable=var_all,
                        command=all_state)
    select_all.grid(row=0,column=1,columnspan=2,sticky=(tk.N,tk.S,tk.E,tk.W))
    select_all.state(['!alternate'])

    for idx, name in enumerate(source):
        if name == "": continue
        row = idx + 1
        #Configure Row
        install_options.rowconfigure(row,weight=1)

        #Resolve Installable Icon
        #Should probably do a search for the appropriate icon or image file.
        #This will be easier once VIS can turn any image into an .ICO or .XBM
        if info[title]["Screens"][name].get("icon") is None:
            img_options.append(PIL.ImageTk.PhotoImage(d_icon.resize((16,16))))

        else:
            scr_icon = info[title]["Screens"][name]["icon"]
            if sys.platform == "win32":
                scr_icon = scr_icon + ".ICO"
            else:
                scr_icon = scr_icon + ".XBM"

            img_options.append(PIL.ImageTk.PhotoImage(Image.open(archive.open("Icons/"+scr_icon)).resize((16,16))))
        #Create Checkbox in List
        var_options.append(tk.IntVar())
        all_options.append(ttk.Checkbutton(install_options,
                                        text=name,
                                        variable=var_options[-1],
                                        command=is_all,
                                        image=img_options[-1],
                                        compound=tk.LEFT))
        all_options[-1].grid(row=row,column=2,sticky=(tk.N,tk.S,tk.E,tk.W))
        all_options[-1].state(['!alternate'])

        #Screen version label
        if show_versions:
            scr_info = info[title]["Screens"].get(name, {})
            scr_ver = scr_info.get("version", "")
            if scr_ver:
                ver_lbl = ttk.Label(install_options, text=f"v{scr_ver}", foreground="gray40")
                ver_lbl.grid(row=row, column=3, sticky=(tk.E,), padx=(0, 8))

makechecks(installables)

#File Location
file_location = tk.StringVar()

file_location.set(platformdirs.user_config_path(appauthor=info[title]["metadata"].get("company"),appname=title))


fframe = ttk.Frame(root)
fframe.grid(row=2,column=1,columnspan=2,sticky=(tk.N,tk.S,tk.E,tk.W))

fframe.rowconfigure(1, weight=1)
fframe.columnconfigure(1,weight=1,minsize=250)
fframe.columnconfigure(2,weight=1,minsize=110)

file = ttk.Label(fframe,textvariable=file_location,relief="sunken")
file.grid(row=1,column=1,padx=2,pady=8,sticky=(tk.N,tk.S,tk.E,tk.W))

def select():
    """Select the file location"""
    selection = filedialog.askdirectory(initialdir=file_location.get(), title="Select Installation Directory")
    if selection not in ["", None]:
        file_location.set(selection)

#File Location Selection
fs = ttk.Button(fframe,
                text="Select Directory",
                command=select)
fs.grid(row=1,column=2,padx=2,pady=4,sticky=(tk.N,tk.S,tk.E,tk.W))

#Frame to beautify the controls
control = ttk.Frame(root)
control.grid(row=3,column=1,columnspan=2,sticky=(tk.N,tk.S,tk.E,tk.W))

control.rowconfigure(1,weight=1)
control.columnconfigure(0,weight=1)
control.columnconfigure(1,weight=1)
control.columnconfigure(2,weight=1)

def previous():
    global next_btn
    next_btn = ttk.Button(control,text="Next",command=nextpage)
    next_btn.grid(row=1,column=2,padx=2,pady=4,sticky=(tk.N,tk.S,tk.E,tk.W))

    for w in install_options.winfo_children():
        w.destroy()

    header["text"] = "Select Installables"
    makechecks(installables)

#Back Button
back = ttk.Button(control, text="Back", command=previous)
back.grid(row=1,column=1,padx=2,pady=4,sticky=(tk.N,tk.S,tk.E,tk.W))

#Close Button
close = ttk.Button(control,text="Close",command=root.destroy)
close.grid(row=1,column=0,padx=2,pady=4,sticky=(tk.N,tk.S,tk.E,tk.W))

def binstall(desktop:list[str], selected_screens:list[str]):
    """Installs the selected binaries"""
    close.state(["disabled"])
    fs.state(["disabled"])
    install_options.unbind("<Configure>")
    install_options.destroy()

    root.update()

    if file_location.get().endswith(f"/{title}") or file_location.get().endswith(f"\\{title}"):
        location = Path(file_location.get())
    else:
        location = Path(file_location.get(),title)

    adjacents(location)#Install adjacent files

    # Build the full list of files to install and compute total size
    adjacent_prefixes = (".VIS/", "Images/", "Icons/", "_internal/")
    install_files = []
    for file in archive.namelist():
        if file.startswith(adjacent_prefixes):
            install_files.append(file)
    for i in selected_screens:
        for file in archive.namelist():
            if (file == i or file.startswith(i + ".") or file.startswith(i + "/")) and file not in install_files:
                install_files.append(file)

    total_size = sum(archive.getinfo(f).file_size for f in install_files)
    installed_size = 0

    def fmt_size(b):
        if b < 1024:
            return f"{b} B"
        elif b < 1024 * 1024:
            return f"{b / 1024:.1f} KB"
        else:
            return f"{b / (1024 * 1024):.1f} MB"

    # Replace canvas with progress UI
    canvas.delete("all")
    progress_frame = ttk.Frame(canvas)
    canvas.create_window((0, 0), window=progress_frame, anchor="nw",
                         width=canvas.winfo_width() or 360)

    file_label = ttk.Label(progress_frame, text="Preparing...", anchor="w")
    file_label.pack(fill="x", padx=8, pady=(12, 2))

    progress_bar = ttk.Progressbar(progress_frame, maximum=100, value=0)
    progress_bar.pack(fill="x", padx=8, pady=2)

    stats_frame = ttk.Frame(progress_frame)
    stats_frame.pack(fill="x", padx=8, pady=(2, 8))
    size_label = ttk.Label(stats_frame, text=f"0 B / {fmt_size(total_size)}", anchor="w")
    size_label.pack(side="left")
    pct_label = ttk.Label(stats_frame, text="0%", anchor="e")
    pct_label.pack(side="right")

    root.update()

    # Extract adjacent and binary files in a single pass
    for file in install_files:
        file_label.config(text=file)
        if file.startswith(adjacent_prefixes):
            archive.extract(file, location)
        else:
            extal(file, location)
        installed_size += archive.getinfo(file).file_size
        pct = int(installed_size * 100 / total_size) if total_size > 0 else 100
        progress_bar.config(value=pct)
        size_label.config(text=f"{fmt_size(installed_size)} / {fmt_size(total_size)}")
        pct_label.config(text=f"{pct}%")
        root.update()

    # Create desktop shortcuts
    actual_shortcuts = []
    for idx, name in enumerate(desktop):
        if var_options[idx].get() == 1:
            file_label.config(text=f"Creating shortcut: {name}")
            root.update()
            shortcut(name, location)
            actual_shortcuts.append(name)

    # Write install log and register in Add/Remove Programs
    file_label.config(text="Registering installation...")
    root.update()
    write_install_log(location, selected_screens, actual_shortcuts)
    register_uninstall(location)

    file_label.config(text="Installation complete.")
    progress_bar.config(value=100)
    pct_label.config(text="100%")
    close.state(["!disabled"])

    # Auto-launch checkbox
    launch_var = tk.IntVar(value=1)
    default_screen = info[title].get("defaults", {}).get("default_screen")
    launch_target = None
    if default_screen and default_screen in selected_screens:
        launch_target = default_screen
    elif selected_screens:
        launch_target = selected_screens[0]

    if launch_target:
        launch_check = ttk.Checkbutton(progress_frame, text=f"Launch {title}",
                                       variable=launch_var)
        launch_check.pack(pady=(4, 8))
        launch_check.state(['!alternate'])

        def _close_and_maybe_launch():
            archive.close()
            if launch_var.get():
                if sys.platform == "win32":
                    exe = os.path.join(location, launch_target + ".exe")
                else:
                    exe = os.path.join(location, launch_target)
                if os.path.exists(str(exe)):
                    subprocess.Popen([str(exe)], cwd=str(location))
            root.destroy()

        close.config(command=_close_and_maybe_launch)
    else:
        close.config(command=lambda: (archive.close(), root.destroy()))

    root.update()

def nextpage():
    """Goes to the next installer page"""
    next_btn.destroy()

    for w in install_options.winfo_children():
        w.destroy()

    selected_screens = []
    for idx in range(len(var_options)):
        if var_options[idx].get() == 1:
            selected_screens.append(installables[idx])

    header["text"] = "Select Desktop Shortcuts"
    makechecks(selected_screens, show_versions=False)

    #Install Button
    install = ttk.Button(control, text="Install",command=lambda: binstall(selected_screens, selected_screens))
    install.grid(row=1,column=2,padx=2,pady=4,sticky=(tk.N,tk.S,tk.E,tk.W))

next_btn = ttk.Button(control,text="Next",command=nextpage)
next_btn.grid(row=1,column=2,padx=2,pady=4,sticky=(tk.N,tk.S,tk.E,tk.W))

root.mainloop()
