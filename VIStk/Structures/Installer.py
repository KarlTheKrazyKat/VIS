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
import shutil
import subprocess
import datetime
import tempfile
import platformdirs
if sys.platform == "win32": import winshell
from pathlib import Path

QUIET = False
FORCE_KILL = False
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

def _on_force(args):
    global FORCE_KILL
    FORCE_KILL = True

def _on_help(args):
    print("Usage: Installer.exe [--Quiet [screens...]] [--Desktop <screens...>] [--Path <dir>] [--Force] [--Verify] [--Help]")
    print()
    print("Flags:")
    print("  --Quiet   [s1] [s2] ...  Install silently (no GUI); installs all screens if none listed")
    print("  --Desktop <s1> <s2> ...  Create desktop shortcuts for listed screens (requires --Quiet)")
    print("  --Path    <directory>    Override the install location (requires --Quiet)")
    print("  --Force                  Force-stop running app processes during update (requires --Quiet)")
    print("  --Verify                 Verify an existing installation's file integrity and exit")
    print("  --Help                   Show this message and exit")
    print()
    print("If no flags are given, the GUI installer will launch.")
    sys.exit(0)

def _on_verify(args):
    global custom_path
    if custom_path:
        v_loc = Path(custom_path)
    else:
        comp = None   # archive not loaded yet at handler time; use platformdirs default
        v_loc = None  # resolved after archive loads below
    # Store flag; actual verify runs after archive loads
    _VERIFY_MODE[0] = True

_VERIFY_MODE = [False]  # mutable flag so _on_verify can set it before archive loads

handler = ArgHandler()
handler.newFlag("Quiet", _on_quiet)
handler.newFlag("Desktop", _on_desktop)
handler.newFlag("Path", _on_path)
handler.newFlag("Help", _on_help)
handler.newFlag("Verify", _on_verify)
handler.newFlag("Force", _on_force)
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
_ALWAYS_INSTALL = {"Uninstaller"}  # binaries extracted on every install, not user-selectable

# Separate tabbed screens (run inside Host) from standalone screens (own exe)
_tabbed_screens = set()
_standalone_screens = set()
for sname, scfg in info[title]["Screens"].items():
    if scfg.get("tabbed", False):
        _tabbed_screens.add(sname)
    else:
        _standalone_screens.add(sname)

# Build the installables list:
# - One entry for the project title (Host + all tabbed screens)
# - One entry per standalone screen
installables = [title]  # Host group is always first
_archive_binaries = set()
for i in archive.namelist():
    if not any(breaker in i for breaker in ["Icons/","Images/",".VIS/","Screens/","modules/",".Runtime/","Shared/"]):
        if "." in i:
            name = ".".join(i.split(".")[:-1])
        else:
            name = i
        if name:
            _archive_binaries.add(name)

for name in _archive_binaries:
    if name in _standalone_screens and name not in installables:
        installables.append(name)

# Detect license/EULA file in archive
_license_text = None
for _lname in ("LICENSE", "LICENSE.txt", "EULA.txt", "EULA.md"):
    if _lname in archive.namelist():
        with archive.open(_lname) as _lf:
            _license_text = _lf.read().decode("utf-8", errors="replace")
        break

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

# Prefixes for files that keep their directory structure during extraction
_dir_prefixes = (".VIS/", "Images/", "Icons/", "Screens/", "modules/", ".Runtime/", "Shared/")

def extal(file, location):
    """Extracts file to the location. Only chmod binaries on Linux."""
    archive.extract(file, location)
    if sys.platform == "linux":
        # Only chmod files that are actual binaries (no extension or .sh)
        basename = os.path.basename(file)
        if "." not in basename or basename.endswith(".sh"):
            subprocess.call(f"chmod +x {os.path.join(location,file)}", shell=True)

def adjacents(location):
    """Installs adjacent files from .VIS, Images, Icons, .Runtime"""
    vis_dir = os.path.join(location, ".VIS")
    runtime_dir = os.path.join(location, ".Runtime")
    os.makedirs(vis_dir, exist_ok=True)
    os.makedirs(os.path.join(location, "Images"), exist_ok=True)
    os.makedirs(os.path.join(location, "Icons"), exist_ok=True)
    os.makedirs(runtime_dir, exist_ok=True)
    if sys.platform == "win32":
        subprocess.call(["attrib", "+h", vis_dir],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.call(["attrib", "+h", runtime_dir],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _find_running_processes(location):
    """Return a list of (pid, name) for app processes running from *location*.

    Checks all screen executables listed in the archive's project.json,
    plus the Uninstaller, against running processes whose exe path is
    inside the install directory.
    """
    results = []
    try:
        import psutil
    except ImportError:
        return results
    install_dir = str(Path(location)).lower()
    for proc in psutil.process_iter(["pid", "name", "exe"]):
        try:
            exe = proc.info.get("exe") or ""
            if exe and exe.lower().startswith(install_dir):
                results.append((proc.info["pid"], proc.info["name"]))
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return results


def _kill_app_processes(location):
    """Terminate all app processes running from *location*.

    Returns the number of processes terminated.
    """
    killed = 0
    try:
        import psutil
    except ImportError:
        return killed
    install_dir = str(Path(location)).lower()
    for proc in psutil.process_iter(["pid", "exe"]):
        try:
            exe = proc.info.get("exe") or ""
            if exe and exe.lower().startswith(install_dir):
                proc.terminate()
                killed += 1
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    # Give processes a moment to exit
    if killed:
        import time
        time.sleep(1)
    return killed


def write_install_log(location, selected_screens, desktop_shortcuts):
    """Write install_log.json recording what was installed."""
    directories = [".VIS", "Icons", "Images", ".Runtime"]

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

    log_path = os.path.join(location, ".VIS", "install_log.json")
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


def verify_installation(location, arc) -> list[str]:
    """Check all installed files exist and match archive sizes.

    Returns a list of issue strings; empty list means everything is OK.
    """
    if arc is None:
        return ["Archive not available — cannot verify."]
    log_path = os.path.join(location, ".VIS", "install_log.json")
    if not os.path.exists(log_path):
        return ["install_log.json not found — cannot verify."]
    try:
        with open(log_path) as f:
            log = json.load(f)
    except Exception as e:
        return [f"Could not read install_log.json: {e}"]

    install_dir = Path(log.get("install_location", str(location)))
    issues = []

    # Check screen executables and adjacent files against archive
    try:
        archive_sizes = {f: arc.getinfo(f).file_size for f in arc.namelist()}
    except Exception as e:
        return [f"Could not read archive: {e}"]
    for scr in log.get("screens", []):
        exe = scr["executable"]
        exe_path = install_dir / exe
        if not exe_path.exists():
            issues.append(f"Missing: {exe}")
        else:
            # Find corresponding archive entry (strip .exe on Windows)
            base = exe.rsplit(".", 1)[0] if "." in exe else exe
            arc_entry = next(
                (f for f in archive_sizes if f == exe or f.startswith(base + ".")),
                None,
            )
            if arc_entry and exe_path.stat().st_size != archive_sizes[arc_entry]:
                issues.append(
                    f"Size mismatch: {exe} "
                    f"(archive {archive_sizes[arc_entry]}B, "
                    f"installed {exe_path.stat().st_size}B)"
                )

    # Check adjacent directories
    for d in log.get("directories", []):
        if not (install_dir / d).exists():
            issues.append(f"Missing directory: {d}")

    return issues


def _should_extract(file: str, location) -> bool:
    """Return True if the file is missing or its content differs from the archive entry."""
    import hashlib
    dest = Path(location) / file
    if not dest.exists():
        return True
    try:
        if dest.stat().st_size != archive.getinfo(file).file_size:
            return True
        return hashlib.sha256(dest.read_bytes()).hexdigest() != hashlib.sha256(archive.read(file)).hexdigest()
    except Exception:
        return True


#%Install & Escape Command Line Args
# Handle --Verify after archive is loaded
if _VERIFY_MODE[0]:
    if custom_path:
        v_loc = Path(custom_path)
    else:
        v_loc = Path(
            platformdirs.user_config_path(
                appauthor=info[title]["metadata"].get("company"), appname=title
            ),
            title,
        )
    issues = verify_installation(v_loc, archive)
    if issues:
        print(f"Integrity check FAILED for {v_loc}:")
        for issue in issues:
            print(f"  {issue}")
    else:
        print(f"All files verified OK ({v_loc}).")
    archive.close()
    sys.exit(0 if not issues else 1)

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

    is_update_quiet = os.path.exists(os.path.join(location, ".VIS", "install_log.json"))

    # Check for running processes in quiet mode
    if is_update_quiet:
        running = _find_running_processes(location)
        if running:
            proc_names = sorted(set(name for _, name in running))
            print(f"  Warning: {len(running)} {title} process(es) still running:")
            for name in proc_names:
                print(f"    - {name}")
            if FORCE_KILL:
                killed = _kill_app_processes(location)
                print(f"  Terminated {killed} process(es).")
            else:
                print(f"  Please close them first, or re-run with --Force to stop them.")
                archive.close()
                sys.exit(1)

    print(f"{'Updating' if is_update_quiet else 'Installing'} {title} v{app_version} to {location}")
    adjacents(location)

    # Collect files to install
    _base_prefixes_q = (".VIS/", "Images/", "Icons/", ".Runtime/")
    _host_prefixes_q = ("Screens/", "modules/", "Shared/")
    # In quiet mode with no screens specified, install everything
    host_selected_q = (not cinstalls) or (title in cinstalls)
    quiet_install_files = []
    for f in archive.namelist():
        if f.startswith(_base_prefixes_q):
            quiet_install_files.append(f)
        elif host_selected_q and f.startswith(_host_prefixes_q):
            quiet_install_files.append(f)
        elif host_selected_q and f.endswith(".py"):
            quiet_install_files.append(f)
        else:
            base = ".".join(f.split(".")[:-1]) if "." in f else f
            if base in _ALWAYS_INSTALL and f not in quiet_install_files:
                quiet_install_files.append(f)
    # If no screens specified in quiet mode, include the Host exe
    if host_selected_q:
        for f in archive.namelist():
            if (f == title or f.startswith(title + ".")) and f not in quiet_install_files:
                quiet_install_files.append(f)
    for i in cinstalls:
        matched = False
        for file in archive.namelist():
            if (file == i or file.startswith(i + ".") or file.startswith(i + "/")) \
                    and file not in quiet_install_files:
                quiet_install_files.append(file)
                matched = True
        if not matched:
            print(f"  Warning: no archive entry matches '{i}'")

    # Update-in-place: skip unchanged files
    quiet_files_to_extract = [f for f in quiet_install_files if _should_extract(f, location)]
    quiet_skipped = len(quiet_install_files) - len(quiet_files_to_extract)
    if quiet_skipped:
        print(f"  Skipping {quiet_skipped} unchanged file(s).")
    if not quiet_files_to_extract:
        print("No changes needed — already up to date.")
        write_install_log(location, cinstalls, dinstalls)
        register_uninstall(location)
        archive.close()
        sys.exit()

    total_size = sum(archive.getinfo(f).file_size for f in quiet_files_to_extract)
    _q_line_w = 70

    def _q_status(text):
        sys.stdout.write(f"\r{text:<{_q_line_w}}")
        sys.stdout.flush()

    # Backup for rollback
    quiet_backup_dir = None
    if is_update_quiet and quiet_files_to_extract:
        quiet_backup_dir = tempfile.mkdtemp(prefix="vis_backup_")
        for idx, file in enumerate(quiet_files_to_extract):
            dest = Path(location) / file
            if dest.exists():
                bk = Path(quiet_backup_dir) / file
                bk.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(dest, bk)
            pct = int((idx + 1) / len(quiet_files_to_extract) * 50)
            _q_status(f"  Backing up [{pct}%] {file[:45]}")
        _q_status("")

    try:
        installed_size = 0
        for file in quiet_files_to_extract:
            if file.startswith(_dir_prefixes) or file.endswith(".py"):
                archive.extract(file, location)
            else:
                extal(file, location)
            installed_size += archive.getinfo(file).file_size
            pct = int(installed_size / total_size * 100) if total_size > 0 else 100
            _q_status(f"  Installing [{pct}%] {file[:45]}")
        _q_status("")
        print()
    except Exception as exc:
        print()
        if quiet_backup_dir and os.path.exists(quiet_backup_dir):
            print("  Extraction failed — restoring backup...")
            for file in quiet_files_to_extract:
                bk = Path(quiet_backup_dir) / file
                if bk.exists():
                    dest = Path(location) / file
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(bk, dest)
            shutil.rmtree(quiet_backup_dir, ignore_errors=True)
        print(f"  Error: {exc}")
        print("Installation failed." + (" Previous installation restored." if is_update_quiet else ""))
        archive.close()
        sys.exit(1)

    if quiet_backup_dir:
        shutil.rmtree(quiet_backup_dir, ignore_errors=True)

    for i in dinstalls:
        print(f"  Creating shortcut: {i}")
        shortcut(i, location)

    write_install_log(location, cinstalls, dinstalls)
    register_uninstall(location)
    print("Installation complete.")
    archive.close()
    sys.exit()

#%Configure Root
root = Root(project=False)
root.withdraw()

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
root.WindowGeometry.setGeometry(width=720,height=400,align="center")
root.minsize(width=720,height=400)
root.deiconify()

#Root Layout
root.rowconfigure(0,weight=1,minsize=30)
root.rowconfigure(1,weight=1,minsize=250)
root.rowconfigure(2,weight=0,minsize=46)
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
version_label = ttk.Label(header_frame, text=f"{title} {app_version}")
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
canvas.bind_all("<MouseWheel>", lambda e: canvas.yview_scroll(-int(e.delta / 120), "units"))

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

        #Resolve Installable Icon and version
        is_host_group = (name == title)
        if is_host_group:
            # Host group uses the project default icon and project version
            img_options.append(PIL.ImageTk.PhotoImage(d_icon.resize((16,16))))
            scr_ver = app_version
        else:
            scr_info = info[title]["Screens"].get(name, {})
            if scr_info.get("icon") is None:
                img_options.append(PIL.ImageTk.PhotoImage(d_icon.resize((16,16))))
            else:
                scr_icon = scr_info["icon"]
                if sys.platform == "win32":
                    scr_icon = scr_icon + ".ico"
                else:
                    scr_icon = scr_icon + ".XBM"
                scr_icon_file = archive.open("Icons/"+scr_icon)
                img_options.append(PIL.ImageTk.PhotoImage(Image.open(scr_icon_file).resize((16,16))))
                scr_icon_file.close()
            scr_ver = scr_info.get("version", "")

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
        if show_versions and scr_ver:
            ver_lbl = ttk.Label(install_options, text=f"{scr_ver}", foreground="gray40")
            ver_lbl.grid(row=row, column=3, sticky=(tk.E,), padx=(0, 8))

# ── EULA / License page ───────────────────────────────────────────────────
_eula_agree_var = tk.IntVar(value=0)

def _show_eula():
    """Display the license agreement in the scrollable area."""
    for w in install_options.winfo_children():
        w.destroy()
    header["text"] = "License Agreement"

    eula_text = tk.Text(install_options, wrap="word", relief="flat",
                        padx=8, pady=8, font=("TkDefaultFont", 9))
    eula_text.insert("1.0", _license_text)
    eula_text.configure(state="disabled")
    eula_text.grid(row=0, column=1, columnspan=3, sticky=(tk.N, tk.S, tk.E, tk.W))
    install_options.rowconfigure(0, weight=1)

    agree_check = ttk.Checkbutton(install_options, text="I agree to the terms above",
                                   variable=_eula_agree_var,
                                   command=_toggle_eula_next)
    agree_check.grid(row=1, column=1, columnspan=3, sticky=(tk.W,), pady=(4, 0))
    agree_check.state(['!alternate'])

def _toggle_eula_next():
    """Enable or disable the Next button based on the agree checkbox."""
    if _eula_agree_var.get() == 1:
        next_btn.state(["!disabled"])
    else:
        next_btn.state(["disabled"])

def _show_installables():
    """Display the installables selection page."""
    global next_btn
    for w in install_options.winfo_children():
        w.destroy()
    header["text"] = "Select Installables"
    makechecks(installables)
    # Ensure Next button goes to shortcuts page
    try: next_btn.destroy()
    except Exception: pass
    next_btn = ttk.Button(control, text="Next", command=nextpage)
    next_btn.grid(row=1, column=2, padx=2, pady=4, sticky=(tk.N, tk.S, tk.E, tk.W))

def _eula_next():
    """Transition from EULA page to installables page."""
    _show_installables()

# Show initial page
if _license_text:
    _show_eula()
else:
    makechecks(installables)

#File Location
file_location = tk.StringVar()

file_location.set(platformdirs.user_config_path(appauthor=info[title]["metadata"].get("company"),appname=title))


fframe = ttk.Frame(root)
fframe.grid(row=2,column=1,columnspan=2,sticky=(tk.N,tk.S,tk.E,tk.W))

fframe.rowconfigure(1, weight=1)
fframe.columnconfigure(1,weight=1,minsize=300)
fframe.columnconfigure(2,weight=0,minsize=130)

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
    if _license_text:
        # Go back to EULA page
        _show_eula()
        next_btn = ttk.Button(control, text="Next", command=_eula_next)
        next_btn.grid(row=1, column=2, padx=2, pady=4, sticky=(tk.N, tk.S, tk.E, tk.W))
        _toggle_eula_next()  # Restore agree-gate state
    else:
        # Go back to installables page
        _show_installables()

#Back Button
back = ttk.Button(control, text="Back", command=previous)
back.grid(row=1,column=1,padx=2,pady=4,sticky=(tk.N,tk.S,tk.E,tk.W))

#Close Button
close = ttk.Button(control,text="Close",command=root.destroy)
close.grid(row=1,column=0,padx=2,pady=4,sticky=(tk.N,tk.S,tk.E,tk.W))

def binstall(desktop:list[str], selected_screens:list[str]):
    """Installs the selected binaries"""
    # Snapshot shortcut selections before destroying the UI
    shortcut_selections = [
        (name, var.get() == 1)
        for name, var in zip(desktop, var_options)
    ]
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

    # Detect existing installation for update-in-place
    existing_log_path = os.path.join(location, ".VIS", "install_log.json")
    is_update = os.path.exists(existing_log_path)

    # Check for running application processes before proceeding
    if is_update:
        running = _find_running_processes(location)
        if running:
            from tkinter import messagebox
            proc_names = sorted(set(name for _, name in running))
            proc_list = "\n".join(f"  - {name}" for name in proc_names)
            msg = (f"The following {title} processes are still running:\n\n"
                   f"{proc_list}\n\n"
                   f"Please close them before updating.\n\n"
                   f"Click Yes to force-stop all {title} processes,\n"
                   f"or No to go back and close them manually.")
            force = messagebox.askyesnocancel(
                f"{title} is running", msg, icon="warning", default="no")
            if force is True:
                killed = _kill_app_processes(location)
                messagebox.showinfo("Processes stopped",
                                    f"Terminated {killed} process(es).")
            elif force is False or force is None:
                close.state(["!disabled"])
                root.update()
                return

    # Build the full list of files to install and compute total size
    _base_prefixes = (".VIS/", "Images/", "Icons/", ".Runtime/")
    _host_prefixes = ("Screens/", "modules/", "Shared/")
    install_files = []
    host_selected = title in selected_screens
    for file in archive.namelist():
        if file.startswith(_base_prefixes):
            install_files.append(file)
        elif host_selected and file.startswith(_host_prefixes):
            install_files.append(file)
        elif host_selected and file.endswith(".py"):
            install_files.append(file)
        else:
            base = ".".join(file.split(".")[:-1]) if "." in file else file
            if base in _ALWAYS_INSTALL and file not in install_files:
                install_files.append(file)
    for i in selected_screens:
        for file in archive.namelist():
            if (file == i or file.startswith(i + ".") or file.startswith(i + "/")) and file not in install_files:
                install_files.append(file)

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

    n_files = max(len(install_files), 1)

    file_label = ttk.Label(progress_frame,
                           text="Checking files..." if is_update else "Preparing...",
                           anchor="w")
    file_label.pack(fill="x", padx=8, pady=(12, 2))

    progress_bar = ttk.Progressbar(progress_frame, maximum=100, value=0)
    progress_bar.pack(fill="x", padx=8, pady=2)

    stats_frame = ttk.Frame(progress_frame)
    stats_frame.pack(fill="x", padx=8, pady=(2, 8))
    size_label = ttk.Label(stats_frame, text=f"0 / {len(install_files)} checked", anchor="w")
    size_label.pack(side="left")
    pct_label = ttk.Label(stats_frame, text="0%", anchor="e")
    pct_label.pack(side="right")

    root.update()

    # Phase 1: Scan — check which files need extracting.
    # The bar fills 0→SCAN_CEILING during scan so it never overshoots
    # and snaps back when backup/extract phases begin.
    SCAN_CEILING = 30
    files_to_extract = []
    for idx, f in enumerate(install_files):
        file_label.config(text=f"Checking: {os.path.basename(f)}")
        pct = int((idx + 1) / n_files * SCAN_CEILING)
        size_label.config(text=f"{idx + 1} / {len(install_files)} checked")
        progress_bar.config(value=pct)
        pct_label.config(text=f"{pct}%")
        root.update()
        if _should_extract(f, location):
            files_to_extract.append(f)

    skipped = len(install_files) - len(files_to_extract)
    total_size = sum(archive.getinfo(f).file_size for f in files_to_extract)
    installed_size = 0

    # Compute proportional phase ranges for the remaining bar space
    n_backup = len(files_to_extract) if (is_update and files_to_extract) else 0
    n_extract = len(files_to_extract)
    remaining = 100 - SCAN_CEILING
    n_work = n_backup + n_extract
    if n_work > 0:
        scan_end = SCAN_CEILING
        backup_end = SCAN_CEILING + int(n_backup / n_work * remaining)
    else:
        scan_end = SCAN_CEILING
        backup_end = SCAN_CEILING

    if not files_to_extract:
        file_label.config(text="No changes needed — already up to date.")
        progress_bar.config(value=100)
        size_label.config(text=f"All {skipped} file(s) unchanged")
        pct_label.config(text="100%")
    else:
        progress_bar.config(value=scan_end)
        pct_label.config(text=f"{scan_end}%")
        file_label.config(text="Updating..." if is_update else "Installing...")
        size_label.config(text=f"0 B / {fmt_size(total_size)}" + (f" ({skipped} unchanged)" if skipped else ""))

    root.update()

    # Phase 2: Back up files that will be overwritten (for rollback on failure)
    backup_dir = None
    if n_backup > 0:
        backup_dir = tempfile.mkdtemp(prefix="vis_backup_")
        for idx, file in enumerate(files_to_extract):
            dest = Path(location) / file
            if dest.exists():
                backup_path = Path(backup_dir) / file
                backup_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(dest, backup_path)
            pct = scan_end + int((idx + 1) / n_backup * (backup_end - scan_end))
            file_label.config(text=f"Backing up: {os.path.basename(file)}")
            progress_bar.config(value=pct)
            pct_label.config(text=f"{pct}%")
            root.update()

    # Phase 3: Extract changed/new files; rollback on failure
    try:
        extract_range = 100 - backup_end
        for file in files_to_extract:
            file_label.config(text=file)
            if file.startswith(_dir_prefixes) or file.endswith(".py"):
                archive.extract(file, location)
            else:
                extal(file, location)
            installed_size += archive.getinfo(file).file_size
            pct = backup_end + (int(installed_size / total_size * extract_range) if total_size > 0 else extract_range)
            progress_bar.config(value=pct)
            size_label.config(text=f"{fmt_size(installed_size)} / {fmt_size(total_size)}"
                              + (f" ({skipped} unchanged)" if skipped else ""))
            pct_label.config(text=f"{pct}%")
            root.update()
    except Exception as exc:
        # Restore backed-up files and abort
        if backup_dir and os.path.exists(backup_dir):
            file_label.config(text="Extraction failed — restoring backup...")
            root.update()
            for file in files_to_extract:
                backup_path = Path(backup_dir) / file
                if backup_path.exists():
                    dest = Path(location) / file
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(backup_path, dest)
            shutil.rmtree(backup_dir, ignore_errors=True)
        from tkinter import messagebox
        messagebox.showerror("Installation failed",
                             f"An error occurred during extraction:\n{exc}\n\n"
                             + ("Previous installation restored." if is_update else ""))
        close.state(["!disabled"])
        root.update()
        return

    # Clean up backup on success
    if backup_dir:
        shutil.rmtree(backup_dir, ignore_errors=True)

    # Create desktop shortcuts
    actual_shortcuts = []
    for name, checked in shortcut_selections:
        if checked:
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
    if default_screen:
        scr_cfg = info[title]["Screens"].get(default_screen, {})
        if scr_cfg.get("tabbed", False):
            # Tabbed screens run inside the Host — launch the Host exe
            launch_target = title
        elif default_screen in selected_screens:
            launch_target = default_screen
    if not launch_target and selected_screens:
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
    try: next_btn.destroy()
    except Exception: pass

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

if _license_text:
    next_btn = ttk.Button(control, text="Next", command=_eula_next)
    next_btn.grid(row=1, column=2, padx=2, pady=4, sticky=(tk.N, tk.S, tk.E, tk.W))
    next_btn.state(["disabled"])  # Disabled until "I agree" is checked
else:
    next_btn = ttk.Button(control, text="Next", command=nextpage)
    next_btn.grid(row=1, column=2, padx=2, pady=4, sticky=(tk.N, tk.S, tk.E, tk.W))

# ── Installer menubar ──────────────────────────────────────────────────────

def _run_uninstaller():
    """Launch the uninstaller from the current install location, if present."""
    loc = file_location.get()
    if loc.endswith(f"/{title}") or loc.endswith(f"\\{title}"):
        inst_dir = Path(loc)
    else:
        inst_dir = Path(loc, title)
    log_path = inst_dir / ".VIS" / "install_log.json"
    if log_path.exists():
        try:
            with open(log_path) as f:
                log = json.load(f)
            inst_dir = Path(log.get("install_location", str(inst_dir)))
        except Exception:
            pass
    uninstaller = inst_dir / ("Uninstaller.exe" if sys.platform == "win32" else "Uninstaller")
    if uninstaller.exists():
        subprocess.Popen([str(uninstaller)], cwd=str(inst_dir))
    else:
        from tkinter import messagebox
        messagebox.showwarning("Uninstaller not found",
                               f"Could not find Uninstaller at:\n{uninstaller}")


def _verify_menu():
    """Run verify_installation against the current install location and show results."""
    from tkinter import messagebox
    loc = file_location.get()
    if loc.endswith(f"/{title}") or loc.endswith(f"\\{title}"):
        inst_dir = Path(loc)
    else:
        inst_dir = Path(loc, title)
    issues = verify_installation(inst_dir, archive)
    if issues:
        messagebox.showwarning(
            "Integrity check failed",
            "\n".join(issues[:20]) + ("\n…and more." if len(issues) > 20 else ""),
        )
    else:
        messagebox.showinfo("Integrity check passed", f"All files verified OK.\n{inst_dir}")


menu_bar = tk.Menu(root)
options_menu = tk.Menu(menu_bar, tearoff=0)
options_menu.add_command(label="Run Uninstaller", command=_run_uninstaller)
options_menu.add_command(label="Verify File Integrity", command=_verify_menu)
menu_bar.add_cascade(label="Options", menu=options_menu)
root.config(menu=menu_bar)

root.mainloop()
