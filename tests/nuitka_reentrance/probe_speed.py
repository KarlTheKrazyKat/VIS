"""Benchmark .pyc vs .pyd for the actual workload screen code does:
function dispatch, attribute access, simple arithmetic, list mutation.

This is roughly representative of what an f_element's loop() or
update() function does: walk some state, update some widgets.  It's
NOT representative of CPU-bound code (numerical computation), which
would show much wider gaps.
"""

import importlib.util
import os
import time


HERE = os.path.dirname(os.path.abspath(__file__))
PYC_PATH = os.path.join(HERE, "build", "pyc", "test_module.pyc")
PYD_PATH = os.path.join(HERE, "build", "test_module.cp313-win_amd64.pyd")


def fresh_load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def time_load(path, n=20):
    """Cold-load timing.  For .pyd we have to use the original
    PyInit name AND avoid the (name,path) cache by copying to unique
    paths — otherwise we measure cache hits, not actual loads."""
    import shutil, tempfile
    elapsed = []
    tmpdir = tempfile.mkdtemp(prefix="speed_")
    try:
        for i in range(n):
            unique = os.path.join(tmpdir, f"copy_{i}_" + os.path.basename(path))
            shutil.copyfile(path, unique)
            t0 = time.perf_counter()
            fresh_load("test_module", unique)
            elapsed.append(time.perf_counter() - t0)
    finally:
        pass  # don't try to clean — pyd files are locked
    return min(elapsed) * 1000, sum(elapsed) / n * 1000


def time_calls(mod, n=100_000):
    """Function-call throughput — bump() and snapshot()."""
    t0 = time.perf_counter()
    for _ in range(n):
        mod.bump()
    bump_time = time.perf_counter() - t0

    t0 = time.perf_counter()
    for _ in range(n):
        mod.snapshot()
    snap_time = time.perf_counter() - t0

    return bump_time * 1000, snap_time * 1000


print(f"PYC: {PYC_PATH}")
print(f"PYD: {PYD_PATH}\n")

print("--- Cold load timing (spec_from_file_location + exec_module) ---")
pyc_min, pyc_avg = time_load(PYC_PATH)
pyd_min, pyd_avg = time_load(PYD_PATH)
print(f"  .pyc:  min {pyc_min:.3f} ms, avg {pyc_avg:.3f} ms")
print(f"  .pyd:  min {pyd_min:.3f} ms, avg {pyd_avg:.3f} ms")
print(f"  ratio (pyc/pyd): {pyc_avg/pyd_avg:.2f}x")

print("\n--- Call throughput: 100,000 iterations ---")
mod_pyc = fresh_load("test_module", PYC_PATH)
mod_pyd = fresh_load("test_module", PYD_PATH)

bump_pyc, snap_pyc = time_calls(mod_pyc)
bump_pyd, snap_pyd = time_calls(mod_pyd)
print(f"  .pyc bump():     {bump_pyc:.1f} ms")
print(f"  .pyd bump():     {bump_pyd:.1f} ms     ratio: {bump_pyc/bump_pyd:.2f}x")
print(f"  .pyc snapshot(): {snap_pyc:.1f} ms")
print(f"  .pyd snapshot(): {snap_pyd:.1f} ms     ratio: {snap_pyc/snap_pyd:.2f}x")
