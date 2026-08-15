"""Unit tests for ``release_info.compiler`` selection in Release.

Covers the flag mapping (``_compiler_args``) and the pre-flight
validation (``_check_compiler``) that guards it.  Builds Release objects
with ``__new__`` so no real project tree, Nuitka run, or toolchain is
needed — both methods depend only on ``self.compiler`` and the platform.

Run: python tests/test_release_compiler.py
"""
import io
import os
import sys
from contextlib import redirect_stdout

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from VIStk.Structures import _Release
from VIStk.Structures._Release import Release, _COMPILERS, _DEFAULT_COMPILER


_failures = []


def check(label, cond):
    if cond:
        print(f"  PASS  {label}")
    else:
        print(f"  FAIL  {label}")
        _failures.append(label)


def _release(compiler):
    """A Release stub carrying only the attribute these methods read."""
    rel = Release.__new__(Release)
    rel.compiler = compiler
    return rel


def _check_quiet(rel):
    """Run _check_compiler, swallowing its printed guidance."""
    with redirect_stdout(io.StringIO()):
        return rel._check_compiler()


def test_defaults():
    print("\nPlatform defaults")
    check("default is a supported value", _DEFAULT_COMPILER in _COMPILERS)
    if sys.platform == "win32":
        check("windows defaults to msvc", _DEFAULT_COMPILER == "msvc")
        check("windows offers msvc + clang", set(_COMPILERS) == {"msvc", "clang"})
    elif sys.platform == "linux":
        check("linux defaults to gcc", _DEFAULT_COMPILER == "gcc")
    elif sys.platform == "darwin":
        check("macos defaults to clang", _DEFAULT_COMPILER == "clang")


def test_compiler_args():
    print("\nNuitka flag mapping")
    if sys.platform == "win32":
        check("msvc -> --msvc=latest only",
              _release("msvc")._compiler_args() == ["--msvc=latest"])
        # clang on Windows is clang-cl piggy-backing on MSVC, so --msvc
        # must survive alongside --clang, not be replaced by it.
        check("clang -> --msvc=latest + --clang",
              _release("clang")._compiler_args() == ["--msvc=latest", "--clang"])
    elif sys.platform == "linux":
        check("gcc -> no flag", _release("gcc")._compiler_args() == [])
        check("clang -> --clang", _release("clang")._compiler_args() == ["--clang"])
    elif sys.platform == "darwin":
        check("clang -> no flag (native)", _release("clang")._compiler_args() == [])

    # The default must produce exactly what pre-0.6.4 emitted, so an
    # existing project.json with no compiler key builds identically.
    legacy = ["--msvc=latest"] if sys.platform == "win32" else []
    check("default matches pre-0.6.4 flags",
          _release(_DEFAULT_COMPILER)._compiler_args() == legacy)


def test_rejects_unsupported():
    print("\nValidation of unsupported values")
    for bad in ("gcc-14", "MSVC ", "zig", "mingw64", ""):
        if bad in _COMPILERS:
            continue
        check(f"rejects {bad!r}", _check_quiet(_release(bad)) is False)

    if sys.platform != "win32":
        check("rejects msvc off-Windows", _check_quiet(_release("msvc")) is False)
    else:
        check("rejects gcc on Windows", _check_quiet(_release("gcc")) is False)


def test_accepts_supported():
    print("\nValidation of supported values")
    # A supported value may still fail the check when the toolchain is
    # genuinely absent (clang-cl not installed).  What must never happen
    # is rejection *for being an unknown value* — assert on the message.
    for good in _COMPILERS:
        buf = io.StringIO()
        with redirect_stdout(buf):
            rel = _release(good)
            rel._check_compiler()
        check(f"{good!r} is not rejected as unknown",
              "is not supported on" not in buf.getvalue())


def test_windows_clang_lookup():
    if sys.platform != "win32":
        return
    print("\nWindows toolchain discovery")
    vs_path = Release._find_msvc()
    check("vswhere locates a VS install", vs_path is not None)
    if vs_path is None:
        return
    clang = Release._find_clang_cl(vs_path)
    check("clang-cl lookup returns a path or None",
          clang is None or os.path.exists(clang))
    # clang-format / clang-tidy ship with components that do NOT include
    # the compiler, so the probe must key on clang-cl.exe specifically.
    check("lookup does not match clang-format/clang-tidy",
          clang is None or os.path.basename(clang).lower() == "clang-cl.exe")
    # Nuitka derives clang from where cl.exe resolved and never reads
    # $PATH, so a standalone LLVM on PATH must not count as a pass.
    check("lookup ignores $PATH",
          Release._find_clang_cl("Z:/no/such/vs/install") is None)
    print(f"  INFO  VS install : {vs_path}")
    print(f"  INFO  clang-cl   : {clang or 'not installed'}")


def test_msvc_pick_order():
    if sys.platform != "win32":
        return
    print("\nVS installation pick order")
    installs = Release._list_msvc()
    check("at least one C++-capable install", len(installs) > 0)
    if not installs:
        return
    for version, product, path in installs:
        has = "yes" if Release._find_clang_cl(path) else "NO "
        print(f"  INFO  {product:<12} {version:<18} clang-cl={has}  {path}")

    check("_find_msvc returns the first ranked install",
          Release._find_msvc() == installs[0][2])
    # Ordering is (version desc, product rank asc).  The product tie-break
    # is the part that bites: with a Community and a BuildTools install at
    # the same version, Nuitka takes Community, so probing BuildTools for
    # clang-cl green-lights a build that then dies in Scons.
    ranks = [_Release._VS_PRODUCT_RANK.get(p, 99) for _, p, _ in installs]
    versions = [v for v, _, _ in installs]
    tied = [r for r, v in zip(ranks, versions) if v == versions[0]]
    check("tied versions ordered by product rank", tied == sorted(tied))


if __name__ == "__main__":
    test_defaults()
    test_compiler_args()
    test_rejects_unsupported()
    test_accepts_supported()
    test_windows_clang_lookup()
    test_msvc_pick_order()

    print()
    if _failures:
        print(f"{len(_failures)} failure(s): {', '.join(_failures)}")
        sys.exit(1)
    print("All release compiler tests passed.")
