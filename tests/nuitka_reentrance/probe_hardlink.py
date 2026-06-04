"""Does Windows LoadLibrary treat NTFS hardlinks as the same file or
distinct? If distinct, we get path-copy isolation for free (no disk
space cost, no actual I/O — just inode-level aliasing).

Hardlinks are created via os.link() on NTFS. The two paths point at
the same file content but have different path strings.
"""

import importlib.util
import os
import sys


HERE = os.path.dirname(os.path.abspath(__file__))
ORIG = os.path.join(HERE, "build", "test_module.cp313-win_amd64.pyd")
LINK_DIR = os.path.join(HERE, "build", "hardlinks")
os.makedirs(LINK_DIR, exist_ok=True)
LINK1 = os.path.join(LINK_DIR, "test_module_47.cp313-win_amd64.pyd")
LINK2 = os.path.join(LINK_DIR, "test_module_48.cp313-win_amd64.pyd")

for p in (LINK1, LINK2):
    if os.path.exists(p):
        os.remove(p)

try:
    os.link(ORIG, LINK1)
    os.link(ORIG, LINK2)
    print(f"Hardlinks created: {LINK1} and {LINK2}")
except OSError as e:
    print(f"Hardlink creation failed: {e}")
    sys.exit(1)


def fresh_load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


mod1 = fresh_load("test_module", LINK1)
mod2 = fresh_load("test_module", LINK2)

print(f"\n  mod1 is mod2:                  {mod1 is mod2}")
print(f"  mod1.__dict__ is mod2.__dict__: {mod1.__dict__ is mod2.__dict__}")
print(f"  mod1.snapshot is mod2.snapshot: {mod1.snapshot is mod2.snapshot}")

mod1.bump()
s1 = mod1.snapshot()
s2 = mod2.snapshot()
print(f"\n  After mod1.bump():")
print(f"    mod1.snapshot(): {s1}")
print(f"    mod2.snapshot(): {s2}")

if s1["counter"] == 1 and s2["counter"] == 0:
    print("\nVERDICT: Hardlinks give independent DLL loads (Windows treats different paths as different DLLs).")
elif s1["counter"] == s2["counter"]:
    print("\nVERDICT: Hardlinks share DLL state (Windows deduplicates by file identity).")
else:
    print(f"\nVERDICT: Mixed result — s1={s1}, s2={s2}")
