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

root = Root()
root.title("Uninstaller")
root.WindowGeometry.setGeometry(width=480, height=320, align="center")
root.minsize(width=480, height=320)

root.rowconfigure(0, weight=0, minsize=30)
root.rowconfigure(1, weight=1, minsize=200)
root.rowconfigure(2, weight=0, minsize=30)
root.columnconfigure(0, weight=1)

# Header
header = ttk.Label(root, text="Uninstaller", anchor="w")
header.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=8, pady=(8, 0))

# Content area
content = ttk.Frame(root)
content.grid(row=1, column=0, sticky=(tk.N, tk.S, tk.E, tk.W), padx=8, pady=4)
content.columnconfigure(0, weight=1)

if log is None:
    ttk.Label(content, text="No install_log.json found.\n\n"
              "Cannot determine what to uninstall.",
              justify="center").pack(expand=True)
    control = ttk.Frame(root)
    control.grid(row=2, column=0, sticky=(tk.E, tk.W), padx=8, pady=(0, 8))
    ttk.Button(control, text="Close", command=root.destroy).pack(side="right")
    root.mainloop()
    sys.exit(0)

# Show what will be removed
app_name = log.get("app_name", "Application")
app_ver  = log.get("app_version", "")
header.config(text=f"Uninstall {app_name} {app_ver}")

details_frame = ttk.Frame(content)
details_frame.pack(fill="both", expand=True)

info_text = tk.Text(details_frame, wrap="word", height=10, state="disabled",
                    relief="sunken", borderwidth=1)
info_text.pack(fill="both", expand=True)

# Build summary
lines = []
lines.append(f"Application: {app_name}")
lines.append(f"Version: {app_ver}")
lines.append(f"Location: {log.get('install_location', location)}")
lines.append("")
screens = log.get("screens", [])
if screens:
    lines.append(f"Screens ({len(screens)}):")
    for s in screens:
        lines.append(f"  {s['name']} ({s.get('executable', '')})")
shortcuts = log.get("desktop_shortcuts", [])
if shortcuts:
    lines.append("")
    lines.append(f"Desktop shortcuts: {', '.join(shortcuts)}")
dirs = log.get("directories", [])
if dirs:
    lines.append("")
    lines.append(f"Directories ({len(dirs)}):")
    for d in dirs:
        lines.append(f"  {d}/")
if log.get("registry_key"):
    lines.append("")
    lines.append(f"Registry: {log['registry_key']}")

info_text.config(state="normal")
info_text.insert("1.0", "\n".join(lines))
info_text.config(state="disabled")

# Controls
control = ttk.Frame(root)
control.grid(row=2, column=0, sticky=(tk.E, tk.W), padx=8, pady=(0, 8))
control.columnconfigure(0, weight=1)
control.columnconfigure(1, weight=1)

close_btn = ttk.Button(control, text="Close", command=root.destroy)
close_btn.grid(row=0, column=0, padx=2, sticky=(tk.W,))


def _do_uninstall():
    """Run the uninstall process with progress UI."""
    uninstall_btn.state(["disabled"])
    close_btn.state(["disabled"])

    # Replace details with progress
    for w in details_frame.winfo_children():
        w.destroy()

    progress_label = ttk.Label(details_frame, text="Preparing...", anchor="w")
    progress_label.pack(fill="x", padx=4, pady=(8, 2))

    progress_bar = ttk.Progressbar(details_frame, maximum=100, value=0)
    progress_bar.pack(fill="x", padx=4, pady=2)

    status_label = ttk.Label(details_frame, text="", anchor="w")
    status_label.pack(fill="x", padx=4, pady=(2, 8))

    root.update()

    # Remove shortcuts
    progress_label.config(text="Removing desktop shortcuts...")
    root.update()
    remove_desktop_shortcuts(log)

    # Remove registry
    progress_label.config(text="Removing registry entry...")
    root.update()
    remove_registry_entry(log)

    # Remove files and directories
    def _gui_progress(step, total, label):
        progress_label.config(text=label)
        pct = int(step * 100 / total) if total > 0 else 100
        progress_bar.config(value=pct)
        status_label.config(text=f"{step}/{total}")
        root.update()

    remove_installed_files(log, location, progress_fn=_gui_progress)

    progress_label.config(text="Uninstallation complete.")
    progress_bar.config(value=100)
    close_btn.state(["!disabled"])

    def _close_and_cleanup():
        schedule_self_delete()
        root.destroy()

    close_btn.config(command=_close_and_cleanup)
    root.update()


uninstall_btn = ttk.Button(control, text="Uninstall", command=_do_uninstall)
uninstall_btn.grid(row=0, column=1, padx=2, sticky=(tk.E,))

root.mainloop()
