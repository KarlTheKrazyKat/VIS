"""Test the core claim of the .pyc-in-.pyd wrapper idea:

Can a .pyc-loaded module be fully unloaded — including all its
module-level objects — by removing it from sys.modules?

Setup:
  1. Compile test_module.py to test_module.pyc.
  2. Load it fresh multiple times via spec_from_file_location.
  3. Verify: (a) each load gives an independent module instance,
            (b) dropping sys.modules entries actually frees memory.

If both pass, the wrapper architecture is sound: each tab gets its
own module via the wrapper, tab close drops the module, GC frees it.
"""

import compileall
import gc
import importlib.util
import os
import sys
import weakref


HERE = os.path.dirname(os.path.abspath(__file__))
PY_SRC = os.path.join(HERE, "test_module.py")
PYC_DIR = os.path.join(HERE, "build", "pyc")
os.makedirs(PYC_DIR, exist_ok=True)
PYC_PATH = os.path.join(PYC_DIR, "test_module.pyc")

# Build a .pyc next to a copy of test_module.py
py_copy = os.path.join(PYC_DIR, "test_module.py")
if not os.path.exists(py_copy) or os.path.getmtime(py_copy) < os.path.getmtime(PY_SRC):
    import shutil
    shutil.copyfile(PY_SRC, py_copy)

compileall.compile_file(py_copy, legacy=True)
# legacy=True puts the .pyc next to the .py as foo.pyc rather than in __pycache__
print(f"Compiled: {PYC_PATH} (exists: {os.path.exists(PYC_PATH)})\n")


def fresh_load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ── Test 1: independent instances ─────────────────────────────────────
print("--- Test 1: per-load isolation ---")
mod1 = fresh_load("test_module_t1", PYC_PATH)
mod2 = fresh_load("test_module_t2", PYC_PATH)
print(f"  mod1 is mod2:           {mod1 is mod2}")
print(f"  mod1.__dict__ is mod2.__dict__: {mod1.__dict__ is mod2.__dict__}")
mod1.bump()
s1, s2 = mod1.snapshot(), mod2.snapshot()
print(f"  After mod1.bump(): mod1={s1}, mod2={s2}")
mod2.bump()
print(f"  After mod2.bump(): mod1={mod1.snapshot()}, mod2={mod2.snapshot()}")
isolated = mod1.snapshot()["counter"] == 1 and mod2.snapshot()["counter"] == 1
print(f"  ISOLATED: {isolated}")


# ── Test 2: can we actually free a .pyc-loaded module? ────────────────
print("\n--- Test 2: garbage collection after sys.modules drop ---")

# Put module into sys.modules so it has the "normal" reference set
sys.modules["test_module_t1"] = mod1
sys.modules["test_module_t2"] = mod2

# Weak references — track whether the underlying objects get freed
wr_mod1 = weakref.ref(mod1)
wr_dict1 = weakref.ref(mod1.__dict__) if hasattr(mod1.__dict__, "__weakref__") else None

# This is the only test that matters: drop sys.modules entry, drop local
# refs, force GC, see if the module disappeared.
del sys.modules["test_module_t1"]
del mod1
gc.collect()

if wr_mod1() is None:
    print(f"  mod1: FREED (weakref dead after GC)")
else:
    print(f"  mod1: STILL ALIVE (weakref returns {wr_mod1()!r})")
    referrers = gc.get_referrers(wr_mod1())
    print(f"    Referrers: {[type(r).__name__ for r in referrers]}")

# mod2 is still alive (still in sys.modules and as local var)
if wr_mod1() is None:
    print(f"  mod2 still alive (control): {mod2.snapshot()}")


# ── Test 3: load many, drop all, verify all freed ─────────────────────
print("\n--- Test 3: many load/drop cycles, check no memory leak ---")
import tracemalloc
tracemalloc.start()

baseline_snap = tracemalloc.take_snapshot()
weak_refs = []

for i in range(50):
    name = f"test_module_cycle_{i}"
    m = fresh_load(name, PYC_PATH)
    sys.modules[name] = m
    m.bump()
    m.bump()
    weak_refs.append(weakref.ref(m))
    # Immediately drop
    del sys.modules[name]
    del m

gc.collect()
final_snap = tracemalloc.take_snapshot()
alive = sum(1 for w in weak_refs if w() is not None)
print(f"  Cycled 50 load/drop iterations.")
print(f"  Module objects still alive after GC: {alive}/50")

stats = final_snap.compare_to(baseline_snap, 'lineno')
total_diff_kb = sum(stat.size_diff for stat in stats[:20]) / 1024
print(f"  Top-20 memory delta:    {total_diff_kb:+.1f} KB")
print(f"  (Modest growth is normal — import system caches.  Large growth would")
print(f"   indicate per-load leak.)")
tracemalloc.stop()
