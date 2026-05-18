"""Test what we can do to a .pyd file AFTER it's been loaded.

Two things we'd like to know:

A. Can we DELETE the .pyd after LoadLibrary maps it?
   - If yes: we free disk space immediately on load, only memory is consumed.
   - If no: disk copy persists until tab close (and we delete it then).

B. Can we RENAME the .pyd after LoadLibrary maps it?
   - If yes: we can free the original filename so another copy can use it.
   - If no: the path is locked while the DLL is mapped.

C. Bonus: does the loaded module keep working after we delete/rename?
   - If yes: the DLL contents are fully in memory, file is just a starting
     point, and we can free disk space without losing functionality.
"""

import importlib.util
import os
import shutil
import sys


HERE = os.path.dirname(os.path.abspath(__file__))
ORIG = os.path.join(HERE, "build", "test_module.cp313-win_amd64.pyd")
TEST_DIR = os.path.join(HERE, "build", "filelock")
os.makedirs(TEST_DIR, exist_ok=True)


def fresh_load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def header(s):
    print(f"\n--- {s} ---")


# ── Test A: delete after load ─────────────────────────────────────────
header("A. Delete .pyd after load")
copy_a = os.path.join(TEST_DIR, "test_module_a.cp313-win_amd64.pyd")
shutil.copyfile(ORIG, copy_a)
mod_a = fresh_load("test_module", copy_a)
mod_a.bump()
print(f"  mod_a.counter after bump: {mod_a.counter}")
try:
    os.remove(copy_a)
    print(f"  os.remove(): SUCCEEDED — file gone while DLL is mapped")
    file_gone = not os.path.exists(copy_a)
    print(f"  File no longer on disk: {file_gone}")
except OSError as e:
    print(f"  os.remove(): FAILED — {type(e).__name__}: {e}")

# Does the loaded module still work?
try:
    mod_a.bump()
    print(f"  mod_a.counter after second bump (post-delete attempt): {mod_a.counter}")
    print(f"  Module still functional: YES")
except Exception as e:
    print(f"  Module post-delete: FAILED — {type(e).__name__}: {e}")


# ── Test B: rename after load ─────────────────────────────────────────
header("B. Rename .pyd after load")
copy_b = os.path.join(TEST_DIR, "test_module_b.cp313-win_amd64.pyd")
renamed_b = os.path.join(TEST_DIR, "test_module_b_renamed.cp313-win_amd64.pyd")
shutil.copyfile(ORIG, copy_b)
mod_b = fresh_load("test_module", copy_b)
mod_b.bump()
print(f"  mod_b.counter after bump: {mod_b.counter}")
try:
    os.rename(copy_b, renamed_b)
    print(f"  os.rename(): SUCCEEDED — file moved while DLL is mapped")
    print(f"  Original path exists: {os.path.exists(copy_b)}")
    print(f"  New path exists: {os.path.exists(renamed_b)}")
except OSError as e:
    print(f"  os.rename(): FAILED — {type(e).__name__}: {e}")

try:
    mod_b.bump()
    print(f"  mod_b.counter after second bump (post-rename): {mod_b.counter}")
    print(f"  Module still functional: YES")
except Exception as e:
    print(f"  Module post-rename: FAILED — {type(e).__name__}: {e}")


# ── Test C: can we copy original-filename .pyd again after rename? ────
header("C. After renaming, can a fresh copy take the freed name?")
if not os.path.exists(copy_b):
    try:
        shutil.copyfile(ORIG, copy_b)
        print(f"  Copied original onto freed path: SUCCEEDED")
        mod_b2 = fresh_load("test_module", copy_b)
        mod_b2.bump()
        print(f"  Loaded freshly-copied .pyd as new module: counter={mod_b2.counter}")
        print(f"  mod_b.counter (old): {mod_b.counter}")
        print(f"  Independent instances: {mod_b.counter != mod_b2.counter or mod_b is not mod_b2}")
        print(f"  mod_b is mod_b2: {mod_b is mod_b2}")
    except Exception as e:
        print(f"  Re-copy or load FAILED: {type(e).__name__}: {e}")
else:
    print("  Skipping — original path still has the old file (rename didn't free it)")


# ── Cleanup ───────────────────────────────────────────────────────────
header("Cleanup attempt (best-effort)")
for p in (copy_a, copy_b, renamed_b):
    if os.path.exists(p):
        try:
            os.remove(p)
            print(f"  Removed: {p}")
        except OSError as e:
            print(f"  Could not remove (likely locked by loaded DLL): {p}")
