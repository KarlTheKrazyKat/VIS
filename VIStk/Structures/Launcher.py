"""Generic launcher that forwards execution to .Runtime/<self>.exe.

Compiled once by PyInstaller as --onefile --noconsole, then copied for
each application executable. The launcher reads its own filename to
determine which real exe to run from the .Runtime/ subdirectory.
"""
import os
import sys
import subprocess

runtime = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), ".Runtime")
real_exe = os.path.join(runtime, os.path.basename(sys.argv[0]))

if os.path.exists(real_exe):
    sys.exit(subprocess.Popen([real_exe] + sys.argv[1:]).wait())
else:
    from tkinter import messagebox
    messagebox.showerror("Launch Error",
                         f"Could not find:\n{real_exe}\n\nThe application may need to be reinstalled.")
    sys.exit(1)
