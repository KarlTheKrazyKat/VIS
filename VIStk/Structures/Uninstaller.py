"""VIStk Uninstaller — GUI and CLI modes.

Reads ``install_log.json`` from the installation directory, removes all
installed files, desktop shortcuts, and the Windows Add/Remove Programs
registry entry.  Schedules self-deletion on Windows.

CLI usage::

    Uninstaller.exe [--Quiet] [--Path <dir>] [--Help]
"""

from VIStk.Objects import Root
from VIStk.Objects._ArgHandler import ArgHandler
import tkinter as tk
from tkinter import ttk
from PIL import Image
import PIL.ImageTk
import sys
import json
import os
import shutil
import subprocess
import platformdirs
from pathlib import Path

QUIET = False
custom_path = None


def _on_quiet(args):
    global QUIET
    QUIET = True


def _on_path(args):
    global custom_path
    if args:
        custom_path = " ".join(args)


def _on_help(args):
    print("Usage: Uninstaller.exe [--Quiet] [--Path <dir>] [--Help]")
    print()
    print("Flags:")
    print("  --Quiet              Uninstall silently (no GUI)")
    print("  --Path <directory>   Override the install location")
    print("  --Help               Show this message and exit")
    sys.exit(0)


handler = ArgHandler()
handler.newFlag("Quiet", _on_quiet)
handler.newFlag("Path", _on_path)
handler.newFlag("Help", _on_help)
handler.handle(sys.argv)


# ── Locate install_log.json ──────────────────────────────────────────────────

def _find_install_log():
    """Return the parsed install_log.json dict and its parent directory."""
    if custom_path:
        log_path = os.path.join(custom_path, "install_log.json")
    elif getattr(sys, "frozen", False):
        # Running as compiled exe — log is in same directory
        log_path = os.path.join(os.path.dirname(sys.executable), "install_log.json")
    else:
        # Development fallback
        log_path = os.path.join(os.path.dirname(__file__), "install_log.json")

    if not os.path.exists(log_path):
        return None, None

    with open(log_path, "r") as f:
        log = json.load(f)
    return log, os.path.dirname(log_path)


# ── Core uninstall logic ─────────────────────────────────────────────────────

def remove_desktop_shortcuts(log):
    """Delete desktop shortcuts listed in the install log."""
    for name in log.get("desktop_shortcuts", []):
        if sys.platform == "win32":
            try:
                import winshell
                lnk = os.path.join(winshell.desktop(), f"{name}.lnk")
                if os.path.exists(lnk):
                    os.remove(lnk)
            except Exception:
                pass
        else:
            try:
                desktop = str(platformdirs.user_desktop_path())
                dt_file = os.path.join(desktop, f"{name}.desktop")
                if os.path.exists(dt_file):
                    os.remove(dt_file)
            except Exception:
                pass


def remove_registry_entry(log):
    """Remove the Add/Remove Programs registry key."""
    if sys.platform != "win32":
        return
    registry_key = log.get("registry_key", "")
    if not registry_key:
        return
    # Extract the subkey path (strip HKCU\\ prefix)
    prefix = "HKCU\\"
    if registry_key.startswith(prefix):
        subkey = registry_key[len(prefix):]
    else:
        subkey = registry_key
    try:
        import winreg
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, subkey)
    except Exception:
        pass


def remove_installed_files(log, location, progress_fn=None):
    """Remove screen executables, directories, and install_log.json.

    *progress_fn* is called with ``(step: int, total: int, label: str)``
    for each operation.
    """
    steps = []

    # Screen executables
    for scr in log.get("screens", []):
        exe = scr.get("executable", "")
        if exe:
            steps.append(("file", os.path.join(location, exe), exe))

    # Directories (reversed so _internal/sub comes before _internal)
    dirs = sorted(log.get("directories", []), key=len, reverse=True)
    for d in dirs:
        steps.append(("dir", os.path.join(location, d), d))

    # install_log.json itself
    steps.append(("file", os.path.join(location, "install_log.json"), "install_log.json"))

    total = len(steps)
    for i, (kind, path, label) in enumerate(steps):
        if progress_fn:
            progress_fn(i, total, f"Removing {label}")
        try:
            if kind == "file" and os.path.exists(path):
                os.remove(path)
            elif kind == "dir" and os.path.isdir(path):
                shutil.rmtree(path)
        except Exception:
            pass

    if progress_fn:
        progress_fn(total, total, "Done")

    # Try to remove the install directory if empty
    try:
        remaining = os.listdir(location)
        # Only self (the uninstaller exe) should remain
        if len(remaining) <= 1:
            for f in remaining:
                fp = os.path.join(location, f)
                if fp != sys.executable:
                    try:
                        os.remove(fp)
                    except Exception:
                        pass
    except Exception:
        pass


def schedule_self_delete():
    """Schedule deletion of this executable after exit (Windows only)."""
    if sys.platform != "win32" or not getattr(sys, "frozen", False):
        return
    exe = sys.executable
    # Use cmd to wait briefly then delete
    subprocess.Popen(
        f'cmd /c ping 127.0.0.1 -n 3 > NUL & del /f /q "{exe}" & '
        f'rmdir /q "{os.path.dirname(exe)}" 2>NUL',
        shell=True,
        creationflags=subprocess.CREATE_NO_WINDOW
            if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
    )


# ── Quiet mode ───────────────────────────────────────────────────────────────

log, location = _find_install_log()

if log is None:
    if QUIET:
        print("Error: install_log.json not found.")
        sys.exit(1)

if QUIET:
    if log is None:
        sys.exit(1)
    app_name = log.get("app_name", "Application")
    print(f"Uninstalling {app_name}...")

    remove_desktop_shortcuts(log)
    print("  Removed desktop shortcuts")

    remove_registry_entry(log)
    print("  Removed registry entry")

    def _print_progress(step, total, label):
        print(f"  [{step}/{total}] {label}")

    remove_installed_files(log, location, progress_fn=_print_progress)
    print("Uninstallation complete.")

    schedule_self_delete()
    sys.exit(0)


# ── GUI mode ─────────────────────────────────────────────────────────────────

root = Root(project=False)
root.WindowGeometry.setGeometry(width=720, height=360, align="center")
root.minsize(width=720, height=360)

root.rowconfigure(0, weight=1, minsize=30)
root.rowconfigure(1, weight=1, minsize=250)
root.rowconfigure(2, weight=0, minsize=46)
root.rowconfigure(3, weight=1, minsize=30)
root.columnconfigure(1, weight=1, minsize=360)
root.columnconfigure(2, weight=1, minsize=360)

# ── Load app icon ─────────────────────────────────────────────────────────────
d_icon = None
_icon_photo = None
if log is not None:
    try:
        _install_dir = log.get("install_location", location)
        _vis_json = os.path.join(_install_dir, ".VIS", "project.json")
        with open(_vis_json) as _f:
            _pinfo = json.load(_f)
        _ptitle = list(_pinfo.keys())[0]
        # prefer uninstaller_icon, fall back to default icon
        _icon_name = (_pinfo[_ptitle].get("defaults", {}).get("uninstaller_icon")
                      or _pinfo[_ptitle].get("defaults", {}).get("icon", "VIS"))
        _icon_ext = ".ico" if sys.platform == "win32" else ".xbm"
        _icon_path = os.path.join(_install_dir, "Icons", _icon_name + _icon_ext)
        if os.path.exists(_icon_path):
            d_icon = Image.open(_icon_path)
            _icon_photo = PIL.ImageTk.PhotoImage(d_icon)
            root.iconphoto(False, _icon_photo)
    except Exception:
        pass

app_name = log.get("app_name", "Application") if log else "Application"
app_ver  = log.get("app_version", "")          if log else ""
root.title(f"{app_name} Uninstaller")

# ── Header ────────────────────────────────────────────────────────────────────
header_frame = ttk.Frame(root)
header_frame.grid(row=0, column=1, columnspan=2, sticky=(tk.N, tk.S, tk.E, tk.W))
header_frame.columnconfigure(0, weight=1)
header_frame.columnconfigure(1, weight=0)
header = ttk.Label(header_frame, text=f"Uninstall {app_name}" if log else "Uninstaller")
header.grid(row=0, column=0, sticky=(tk.W,), padx=(4, 0))
if app_ver:
    ttk.Label(header_frame, text=f"v{app_ver}").grid(row=0, column=1, sticky=(tk.E,), padx=(0, 8))

# ── No log fallback ───────────────────────────────────────────────────────────
if log is None:
    no_log_frame = ttk.Frame(root)
    no_log_frame.grid(row=1, column=1, columnspan=2, sticky=(tk.N, tk.S, tk.E, tk.W))
    ttk.Label(no_log_frame, text="No install_log.json found.\nCannot determine what to uninstall.",
              justify="center").place(relx=0.5, rely=0.5, anchor="center")

    loc_frame = ttk.Frame(root)
    loc_frame.grid(row=2, column=1, columnspan=2, sticky=(tk.N, tk.S, tk.E, tk.W))

    control = ttk.Frame(root)
    control.grid(row=3, column=1, columnspan=2, sticky=(tk.N, tk.S, tk.E, tk.W))
    control.rowconfigure(1, weight=1)
    control.columnconfigure(0, weight=1)
    ttk.Button(control, text="Close", command=root.destroy).grid(
        row=1, column=0, padx=2, pady=4, sticky=(tk.N, tk.S, tk.E, tk.W))
    root.mainloop()
    sys.exit(0)

# ── Screen checklist ──────────────────────────────────────────────────────────
install_frame = ttk.Frame(root)
install_frame.grid(row=1, column=1, columnspan=2, sticky=(tk.N, tk.S, tk.E, tk.W))

canvas = tk.Canvas(install_frame)
scrollbar = ttk.Scrollbar(install_frame, orient="vertical", command=canvas.yview)
screen_options = ttk.Frame(canvas)

canvas.create_window((0, 0), window=screen_options, anchor="nw")
screen_options.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
canvas.configure(yscrollcommand=scrollbar.set)
canvas.pack(side="left", fill="both", expand=True)
scrollbar.pack(side="right", fill="y")

screen_options.columnconfigure(1, minsize=15, weight=0)
screen_options.columnconfigure(2, weight=1)
screen_options.columnconfigure(3, weight=0, minsize=60)

installed_screens = log.get("screens", [])
var_all   = tk.IntVar()
var_items = []
img_items = []

def _all_state():
    for v in var_items:
        v.set(var_all.get())

def _is_all():
    for v in var_items:
        if v.get() == 0:
            var_all.set(0)
            return
    var_all.set(1)

select_all = ttk.Checkbutton(screen_options, text="All", variable=var_all, command=_all_state)
select_all.grid(row=0, column=1, columnspan=2, sticky=(tk.N, tk.S, tk.E, tk.W))
select_all.state(["!alternate"])

for idx, scr in enumerate(installed_screens):
    row = idx + 1
    screen_options.rowconfigure(row, weight=1)
    name = scr["name"]

    if d_icon is not None:
        img_items.append(PIL.ImageTk.PhotoImage(d_icon.resize((16, 16))))
    else:
        img_items.append(None)

    var_items.append(tk.IntVar(value=1))
    cb = ttk.Checkbutton(screen_options, text=name, variable=var_items[-1], command=_is_all,
                         image=img_items[-1] if img_items[-1] else "", compound=tk.LEFT)
    cb.grid(row=row, column=2, sticky=(tk.N, tk.S, tk.E, tk.W))
    cb.state(["!alternate"])

    scr_ver = scr.get("version", "")
    if scr_ver:
        ttk.Label(screen_options, text=f"v{scr_ver}", foreground="gray40").grid(
            row=row, column=3, sticky=(tk.E,), padx=(0, 8))

var_all.set(1)

# ── Install location display ──────────────────────────────────────────────────
loc_frame = ttk.Frame(root)
loc_frame.grid(row=2, column=1, columnspan=2, sticky=(tk.N, tk.S, tk.E, tk.W))
loc_frame.rowconfigure(1, weight=1)
loc_frame.columnconfigure(1, weight=1)

ttk.Label(loc_frame, textvariable=tk.StringVar(value=log.get("install_location", location)),
          relief="sunken").grid(row=1, column=1, padx=2, pady=8, sticky=(tk.N, tk.S, tk.E, tk.W))

# ── Controls ──────────────────────────────────────────────────────────────────
control = ttk.Frame(root)
control.grid(row=3, column=1, columnspan=2, sticky=(tk.N, tk.S, tk.E, tk.W))
control.rowconfigure(1, weight=1)
control.columnconfigure(0, weight=1)
control.columnconfigure(1, weight=1)
control.columnconfigure(2, weight=1)

close_btn = ttk.Button(control, text="Close", command=root.destroy)
close_btn.grid(row=1, column=0, padx=2, pady=4, sticky=(tk.N, tk.S, tk.E, tk.W))

progress_frame = ttk.Frame(install_frame)  # shown during uninstall

def _do_uninstall():
    selected = [installed_screens[i]["name"] for i, v in enumerate(var_items) if v.get() == 1]
    if not selected:
        return

    uninstall_btn.state(["disabled"])
    close_btn.state(["disabled"])

    # Build a filtered log for the selected screens only
    filtered_log = dict(log)
    filtered_log["screens"] = [s for s in installed_screens if s["name"] in selected]

    # Switch to progress UI
    canvas.pack_forget()
    scrollbar.pack_forget()
    progress_frame.pack(fill="both", expand=True)

    progress_label = ttk.Label(progress_frame, text="Preparing...", anchor="w")
    progress_label.pack(fill="x", padx=8, pady=(12, 2))
    progress_bar = ttk.Progressbar(progress_frame, maximum=100, value=0)
    progress_bar.pack(fill="x", padx=8, pady=2)
    status_label = ttk.Label(progress_frame, text="", anchor="w")
    status_label.pack(fill="x", padx=8, pady=(2, 8))
    root.update()

    progress_label.config(text="Removing desktop shortcuts...")
    root.update()
    remove_desktop_shortcuts(filtered_log)

    all_selected = len(selected) == len(installed_screens)
    if all_selected:
        progress_label.config(text="Removing registry entry...")
        root.update()
        remove_registry_entry(filtered_log)

    def _gui_progress(step, total, label):
        progress_label.config(text=label)
        pct = int(step * 100 / total) if total > 0 else 100
        progress_bar.config(value=pct)
        status_label.config(text=f"{step}/{total}")
        root.update()

    remove_installed_files(filtered_log, location, progress_fn=_gui_progress)

    progress_label.config(text="Uninstallation complete.")
    progress_bar.config(value=100)
    close_btn.state(["!disabled"])
    close_btn.config(command=lambda: (schedule_self_delete() if all_selected else None, root.destroy())
                     if all_selected else root.destroy())
    root.update()


uninstall_btn = ttk.Button(control, text="Uninstall", command=_do_uninstall)
uninstall_btn.grid(row=1, column=2, padx=2, pady=4, sticky=(tk.N, tk.S, tk.E, tk.W))

root.mainloop()
