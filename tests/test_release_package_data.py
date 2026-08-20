"""End-to-end test: a compiled shared package keeps its data files.

Nuitka ``--module`` output contains the Python and nothing else, so a
package that reads a data file relative to ``__file__`` breaks at release
time unless the file is shipped beside the ``.pyd``.  pywomlib is the
motivating case -- its ``__init__`` reads ``paths.json`` at import time.

Builds a throwaway package with a data file, compiles it the way
``_compile_one_shared`` does, runs ``_copy_package_data``, then imports
the result in a subprocess and asserts the data is readable.

Requires a working C toolchain (this compiles for real).
Run: python tests/test_release_package_data.py
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from VIStk.Structures._Release import Release, _MOD_EXT

_failures = []


def check(label, cond):
    if cond:
        print(f"  PASS  {label}")
    else:
        print(f"  FAIL  {label}")
        _failures.append(label)


def _build_pkg(root):
    """A package that reads its own data file at import time."""
    pkg = os.path.join(root, "vistk_probe")
    os.makedirs(os.path.join(pkg, "nested"))
    with open(os.path.join(pkg, "__init__.py"), "w") as f:
        f.write(
            "import json\n"
            "from pathlib import Path\n"
            "cfg = json.loads((Path(__file__).parent / 'cfg.json').read_text())\n"
        )
    with open(os.path.join(pkg, "mod.py"), "w") as f:
        f.write("VALUE = 7\n")
    with open(os.path.join(pkg, "cfg.json"), "w") as f:
        json.dump({"marker": "from-data-file"}, f)
    with open(os.path.join(pkg, "nested", "deep.bin"), "wb") as f:
        f.write(b"\x00deep")
    return pkg


def main():
    tmp = tempfile.mkdtemp(prefix="vistk_pkgdata_")
    try:
        pkg_dir = _build_pkg(tmp)
        runtime = os.path.join(tmp, "runtime")
        out = os.path.join(tmp, "out")
        os.makedirs(runtime)

        print("\nCompiling probe package (real Nuitka build)")
        rel = Release.__new__(Release)
        rel.runtime = runtime
        proc = subprocess.run(
            [sys.executable, "-m", "nuitka", "--module",
             "--include-package=vistk_probe", f"--output-dir={out}",
             "--assume-yes-for-downloads", pkg_dir],
            capture_output=True, text=True, cwd=tmp,
        )
        built = [f for f in os.listdir(out) if f.endswith(_MOD_EXT)] \
            if os.path.isdir(out) else []
        check("nuitka produced a module", bool(built))
        if not built:
            print((proc.stderr or proc.stdout)[-800:])
            return
        shutil.move(os.path.join(out, built[0]),
                    os.path.join(runtime, f"vistk_probe{_MOD_EXT}"))

        # Before the fix: compiled .pyd alone, data file absent.
        probe = (
            "import sys, json; sys.path.insert(0, sys.argv[1]);\n"
            "import vistk_probe as p;\n"
            "import vistk_probe.mod as m;\n"
            "print(json.dumps({'marker': p.cfg['marker'], 'sub': m.VALUE,\n"
            "                  'file': p.__file__}))\n"
        )
        before = subprocess.run([sys.executable, "-c", probe, runtime],
                                capture_output=True, text=True)
        check("import fails without data file (reproduces the bug)",
              before.returncode != 0 and "cfg.json" in before.stderr)

        print("\nShipping package data")
        copied = rel._copy_package_data("vistk_probe", pkg_dir)
        check("copied the data files", copied == 2)
        check("no .py shipped alongside",
              not any(f.endswith((".py", ".pyc"))
                      for _r, _d, fs in os.walk(os.path.join(runtime, "vistk_probe"))
                      for f in fs))
        check("data lands in runtime/<pkg>/, not runtime/",
              os.path.exists(os.path.join(runtime, "vistk_probe", "cfg.json"))
              and not os.path.exists(os.path.join(runtime, "cfg.json")))
        check("nested structure preserved",
              os.path.exists(os.path.join(runtime, "vistk_probe", "nested", "deep.bin")))

        print("\nImporting the compiled package with its data")
        after = subprocess.run([sys.executable, "-c", probe, runtime],
                               capture_output=True, text=True)
        check("import now succeeds", after.returncode == 0)
        if after.returncode != 0:
            print(after.stderr[-800:])
            return
        got = json.loads(after.stdout.strip().splitlines()[-1])
        check("data file read at import time", got["marker"] == "from-data-file")
        check("sibling dir does not shadow the .pyd", got["sub"] == 7)
        check("__file__ synthesized inside runtime/<pkg>/",
              os.path.basename(os.path.dirname(got["file"])) == "vistk_probe")

        print("\n  INFO  __file__ =", got["file"])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
    print()
    if _failures:
        print(f"{len(_failures)} failure(s): {', '.join(_failures)}")
        sys.exit(1)
    print("All package-data tests passed.")
