"""Test the "rename a single file between loads" strategy.

User's idea: instead of making N disk copies (one per tab), keep ONE
on-disk file and rename it to a unique path right before each load.
After load, rename it back to the original name so the next tab can do
the same thing.  Net disk cost: 1 file ever, not N.

The open question: when we rename file X to path P1, load it, then
rename it to path P2 and load again, do those two loads share DLL
state (like hardlinks did) or are they independent (like copies)?

The hardlink result suggests Windows tracks DLLs by file identity
(inode equivalent), and renaming preserves identity — so this is
likely to behave like hardlinks and fail to give isolation. Test
confirms it either way.
"""

import importlib.util
import os
import shutil
import sys


HERE = os.path.dirname(os.path.abspath(__file__))
ORIG = os.path.join(HERE, "build", "test_module.cp313-win_amd64.pyd")
TEST_DIR = os.path.join(HERE, "build", "rename_strategy")
os.makedirs(TEST_DIR, exist_ok=True)

# Single working copy that we'll rename between loads
WORK = os.path.join(TEST_DIR, "shared.cp313-win_amd64.pyd")
SLOT1 = os.path.join(TEST_DIR, "slot1.cp313-win_amd64.pyd")
SLOT2 = os.path.join(TEST_DIR, "slot2.cp313-win_amd64.pyd")

if os.path.exists(WORK):
    os.remove(WORK)
shutil.copyfile(ORIG, WORK)


def fresh_load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


print("Strategy: rename ONE file between loads.\n")

# Tab 47: rename shared -> slot1, load
os.rename(WORK, SLOT1)
mod1 = fresh_load("test_module", SLOT1)
print(f"  After load #1: shared exists? {os.path.exists(WORK)}, slot1 exists? {os.path.exists(SLOT1)}")

# Re-copy the original to free up the WORK name (since SLOT1 is now locked by the DLL)
# Without re-copying, the rename strategy can't continue — we need ONE file
# available to rename to slot2.  This already destroys the "ONE file ever"
# pretense, but let's continue to see what the DLL cache does.
shutil.copyfile(ORIG, WORK)
print(f"  Copied original to WORK again.")

# Tab 48: rename shared -> slot2, load
os.rename(WORK, SLOT2)
mod2 = fresh_load("test_module", SLOT2)
print(f"  After load #2: shared exists? {os.path.exists(WORK)}, slot2 exists? {os.path.exists(SLOT2)}")

print(f"\n  mod1 is mod2: {mod1 is mod2}")
print(f"  mod1.__dict__ is mod2.__dict__: {mod1.__dict__ is mod2.__dict__}")

mod1.bump()
s1 = mod1.snapshot()
s2 = mod2.snapshot()
print(f"\n  After mod1.bump():")
print(f"    mod1.snapshot(): {s1}")
print(f"    mod2.snapshot(): {s2}")

if s1["counter"] == 1 and s2["counter"] == 0:
    print(f"\n  VERDICT: Independent — rename-strategy works")
else:
    print(f"\n  VERDICT: Shared/partial — rename doesn't help, must use real copies")

print()
print("Note even if independent: the strategy still requires re-creating")
print("the source file before each load (because the previous file is")
print("locked by its loaded DLL).  Net disk cost is still N copies, just")
print("held under different names.  No actual space savings.")
