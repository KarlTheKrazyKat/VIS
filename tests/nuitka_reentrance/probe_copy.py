"""Test: does copying the .pyd to a unique path defeat Nuitka's slot
retargeting?

CPython's extension cache is keyed on (name, path).  Different paths
mean cache miss.  Windows LoadLibrary is also (we believe) keyed on the
file path, so two copies at different paths should produce two distinct
OS-level DLL handles with independent C-level static state.

If true: copying the .pyd per-tab gives per-tab module instances all
the way down to the C-level slots.  This is the "free" workaround that
doesn't need PE export table manipulation.
"""

import importlib.util
import os
import shutil
import sys


HERE = os.path.dirname(os.path.abspath(__file__))
ORIG = os.path.join(HERE, "build", "test_module.cp313-win_amd64.pyd")
COPY_DIR = os.path.join(HERE, "build", "copies")
os.makedirs(COPY_DIR, exist_ok=True)
COPY1 = os.path.join(COPY_DIR, "test_module_47.cp313-win_amd64.pyd")
COPY2 = os.path.join(COPY_DIR, "test_module_48.cp313-win_amd64.pyd")
shutil.copyfile(ORIG, COPY1)
shutil.copyfile(ORIG, COPY2)


def fresh_load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


print(f"Python: {sys.version}")
print(f"COPY1: {COPY1}")
print(f"COPY2: {COPY2}\n")

# Both loads use the SAME spec name "test_module" but DIFFERENT paths.
# If LoadLibrary truly keys on path, each gets its own DLL handle.
try:
    mod1 = fresh_load("test_module", COPY1)
    print("Load #1: succeeded")
except Exception as e:
    print(f"Load #1 FAILED: {type(e).__name__}: {e}")
    sys.exit(1)

try:
    mod2 = fresh_load("test_module", COPY2)
    print("Load #2: succeeded")
except Exception as e:
    print(f"Load #2 FAILED: {type(e).__name__}: {e}")
    sys.exit(1)

print(f"\n  mod1 is mod2:                              {mod1 is mod2}")
print(f"  mod1.__dict__ is mod2.__dict__:            {mod1.__dict__ is mod2.__dict__}")
print(f"  mod1.snapshot is mod2.snapshot:            {mod1.snapshot is mod2.snapshot}")
print(f"  mod1.snapshot.__globals__ is mod1.__dict__: {mod1.snapshot.__globals__ is mod1.__dict__}")
print(f"  mod2.snapshot.__globals__ is mod2.__dict__: {mod2.snapshot.__globals__ is mod2.__dict__}")

print("\n--- Bump mod1, then sample both via .snapshot() (which uses C-level slots) ---")
mod1.bump()
s1 = mod1.snapshot()
s2 = mod2.snapshot()
print(f"  mod1.snapshot(): {s1}")
print(f"  mod2.snapshot(): {s2}")
print(f"  Direct mod1.__dict__['counter']: {mod1.__dict__['counter']}")
print(f"  Direct mod2.__dict__['counter']: {mod2.__dict__['counter']}")

print("\n--- Bump mod2, sample again ---")
mod2.bump()
s1 = mod1.snapshot()
s2 = mod2.snapshot()
print(f"  mod1.snapshot(): {s1}")
print(f"  mod2.snapshot(): {s2}")
print(f"  Direct mod1.__dict__['counter']: {mod1.__dict__['counter']}")
print(f"  Direct mod2.__dict__['counter']: {mod2.__dict__['counter']}")

# The critical question: does mod1.snapshot() (compiled C body) see
# mod1's state or mod2's state?
mod1_compiled_sees = s1["counter"]
mod1_dict_says = mod1.__dict__["counter"]

print()
if mod1_compiled_sees == mod1_dict_says:
    print("VERDICT: Per-tab isolation WORKS via path-copy.")
    print(f"  mod1's compiled .snapshot() sees counter={mod1_compiled_sees}, matching its own __dict__.")
else:
    print("VERDICT: Path-copy does NOT defeat slot retargeting.")
    print(f"  mod1's __dict__['counter'] = {mod1_dict_says}")
    print(f"  but mod1.snapshot() reports counter = {mod1_compiled_sees}")
    print("  The compiled function body is still reading from a shared C-level slot.")
