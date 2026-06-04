"""Nuitka re-entrance test.

Loads ``test_module`` four ways and reports whether each path gives
independent module instances or a shared/cached one.

The corners we care about:

    A. .py source, two loads, SAME spec name
    B. .py source, two loads, DIFFERENT spec names
    C. .pyd compiled, two loads, SAME spec name
    D. .pyd compiled, two loads, DIFFERENT spec names

For each corner the protocol is:

    1. Load instance #1.
    2. Bump it (counter 0 -> 1, items [] -> [1]).
    3. Load instance #2.  Take a fresh snapshot.
    4. Bump #2 once.
    5. Compare identities and post-state.

Reading the verdict:

    SHARED       -> mod1 is mod2 and counter ends at 2, items at [1, 2]
    INDEPENDENT  -> mod1 is not mod2 and each has its own counter == 1
                    and each has its own items list (different ids)
    PARTIAL      -> anything in between (e.g. distinct module objects but
                    items list shared, indicating C-level static state
                    that's reused even though Python-level dict is fresh)

Run from the directory containing this file:

    python harness.py
"""

import importlib.util
import os
import sys


HERE = os.path.dirname(os.path.abspath(__file__))
PY_PATH = os.path.join(HERE, "test_module.py")
PYD_PATH = os.path.join(HERE, "build", "test_module.cp313-win_amd64.pyd")


def fresh_load(name: str, path: str):
    """Load ``path`` as a module named ``name`` without registering it in
    ``sys.modules`` — the same trick VIStk's _import_screen uses."""
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None:
        raise RuntimeError(f"spec_from_file_location returned None for {path!r}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def verdict(mod1, mod2, after_bump1, after_bump2_initial, after_bump2_final):
    """Classify the relationship between two loaded module instances."""
    same_obj = mod1 is mod2
    final_c1 = mod1.snapshot()["counter"]
    final_c2 = mod2.snapshot()["counter"]
    final_items1 = mod1.snapshot()["items"]
    final_items2 = mod2.snapshot()["items"]
    items_same_id = mod1.snapshot()["items_id"] == mod2.snapshot()["items_id"]

    if same_obj:
        return "SHARED (same module object)"
    if not same_obj and not items_same_id and final_c1 == 1 and final_c2 == 1:
        return "INDEPENDENT (different module objects, separate state)"
    if not same_obj and items_same_id:
        return "PARTIAL (distinct Python module objects, shared C-level state)"
    return f"UNCLEAR (same_obj={same_obj}, items_same_id={items_same_id}, c1={final_c1}, c2={final_c2})"


def run_corner(label: str, name1: str, name2: str, path: str):
    """Run one (path, name1, name2) corner of the matrix."""
    print(f"\n=== {label} ===")
    print(f"  path:  {path}")
    print(f"  name1: {name1!r}")
    print(f"  name2: {name2!r}")

    try:
        mod1 = fresh_load(name1, path)
    except Exception as e:
        print(f"  load #1 FAILED: {type(e).__name__}: {e}")
        return
    s0 = mod1.snapshot()
    print(f"  load #1 initial: counter={s0['counter']}, items={s0['items']}, items_id={s0['items_id']}")
    mod1.bump()
    s1 = mod1.snapshot()
    print(f"  load #1 after bump: counter={s1['counter']}, items={s1['items']}, items_id={s1['items_id']}")

    try:
        mod2 = fresh_load(name2, path)
    except Exception as e:
        print(f"  load #2 FAILED: {type(e).__name__}: {e}")
        return
    s2_initial = mod2.snapshot()
    print(f"  load #2 initial: counter={s2_initial['counter']}, items={s2_initial['items']}, items_id={s2_initial['items_id']}")
    mod2.bump()
    s2_final = mod2.snapshot()
    print(f"  load #2 after bump: counter={s2_final['counter']}, items={s2_final['items']}, items_id={s2_final['items_id']}")

    print(f"  mod1 is mod2: {mod1 is mod2}")
    print(f"  VERDICT: {verdict(mod1, mod2, s1, s2_initial, s2_final)}")


def main():
    if not os.path.exists(PY_PATH):
        print(f"ERROR: {PY_PATH} missing")
        sys.exit(1)
    if not os.path.exists(PYD_PATH):
        print(f"ERROR: {PYD_PATH} missing — did Nuitka build succeed?")
        sys.exit(1)

    print(f"Python:    {sys.version}")
    print(f"PY  path:  {PY_PATH}")
    print(f"PYD path:  {PYD_PATH}")

    run_corner("A. .py  / same name",      "test_module",   "test_module",   PY_PATH)
    run_corner("B. .py  / different names","test_module_a", "test_module_b", PY_PATH)
    run_corner("C. .pyd / same name",      "test_module",   "test_module",   PYD_PATH)
    run_corner("D. .pyd / different names","test_module_a", "test_module_b", PYD_PATH)


if __name__ == "__main__":
    main()
