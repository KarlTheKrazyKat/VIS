from VIStk.Structures._Project import *
from VIStk.Structures._VINFO import *
from VIStk.Structures._Screen import *
from VIStk.Structures._Group import Group
import re as _re
import subprocess
import shutil
import glob
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from os.path import exists
from zipfile import *
import datetime
import hashlib
import importlib.metadata
import json
import marshal
from VIStk.Structures._Version import Version

# Nuitka writes ``.pyd`` on Windows and ``.so`` on Linux/macOS for both
# ``--module`` outputs and the bundled extensions inside a standalone
# ``.dist`` folder.  Globs and rename targets must match the platform —
# hardcoding ``.pyd`` makes every Linux release fail at the first compile
# step (#124).
_MOD_EXT = ".pyd" if sys.platform == "win32" else ".so"

# Executable extension passed to Nuitka's --output-filename and used
# everywhere the install layer reasons about exe names.  Hardcoding
# ``.exe`` produced files like ``AssetManager.exe`` on Linux that
# disagreed with the install_log / is_screen_installed conventions
# (#126).
_EXE_EXT = ".exe" if sys.platform == "win32" else ""


class Release(Project):
    """A VIS Release object"""
    def __init__(self, flag:str="",type:str="",note:str="",
                 release_groups: list[str] | None = None,
                 release_screens: list[str] | None = None):
        """Creates a Release object to release or examine a release of a project

        ``release_groups`` and ``release_screens`` scope the build to a
        subset of screens.  When both are empty/``None``, every releasable
        screen (every tabbed screen + every standalone with
        ``release=true``) is built.  Otherwise only the union of the named
        groups and explicit screens is built; the Host is always included.

        Validation runs in ``__init__`` and prints + sets
        ``self.release_targets`` to ``None`` on any of:
          * unknown group name
          * unknown screen name
          * explicitly-named standalone screen with ``release=false``
          * empty result after applying group/screen filters

        Group-level filtering tolerates ``release=false`` standalones —
        they're warned about and skipped, not fatal.
        """
        super().__init__()
        self.type = type
        self.flag = flag
        self.note = note

        # Deliverables (final dist folders, installers, zips) and Nuitka
        # working dirs (per-flag caches) both live at the project root.
        # release_info.location in project.json is ignored — kept readable
        # for back-compat in case any old project.json still has it.
        self.location = f"{self.p_project}/dist/"

        # ``pendix`` is "<title>" with no flag, or "<title>-<flag>" with one.
        # Used to suffix the final dist folder AND the per-flag Nuitka build
        # cache so concurrent / cross-platform builds do not stomp each
        # other's caches (#91).
        self.pendix = self.title if flag == "" else f"{self.title}-{flag}"
        self.build_dir = f"{self.p_project}/build/{self.pendix}/"
        self.final = f"{self.location}{self.pendix}"
        self.runtime = f"{self.final}/runtime"
        """Subdirectory of ``self.final`` where every Nuitka build merges.

        Holds all .exes, the shared Python runtime (``python3xx.dll`` +
        ``.pyd`` extensions), Tcl/Tk runtime, plus ``Screens/``, ``modules/``,
        ``Icons/``, ``Images/``, ``.VIS/``.  Only ``Uninstaller.exe``
        (PyInstaller --onefile, self-contained) and ``LICENSE`` live at
        ``self.final`` root."""

        # Top-level packages that compile_shared ships as standalone
        # ``<pkg>.pyd`` files at the install root.  Every other phase
        # adds ``--nofollow-import-to={pkg}`` for each of these so its
        # build doesn't bundle a duplicate copy.
        self.shared_pkg_names: list[str] = [
            imp for imp in self.hidden_imports if "." not in imp
        ]
        for pkg in self.collect_packages:
            if pkg not in self.shared_pkg_names:
                self.shared_pkg_names.append(pkg)

        self.release_groups: list[str] = list(release_groups or [])
        self.release_screens: list[str] = list(release_screens or [])
        self.release_targets: list[Screen] | None = self._resolve_release_targets()
        """Screens to compile this build, in project (screenlist) order.

        ``None`` indicates a validation failure — :meth:`release` aborts."""

        # Project-level Nuitka config.  ``onefile`` applies to every
        # entry-script compile (Host + standalones); when true, each
        # produces a single self-contained .exe instead of a .dist
        # folder.  Onefile entries also get a build-time bootstrap
        # wrapper prepended (see :meth:`_make_bootstrap_wrapper`) so
        # external Screens / modules / shared packages still resolve at
        # runtime — Python in onefile mode runs from a temp unpack dir,
        # not the install root, so we have to re-add the install root
        # to ``sys.path`` ourselves.
        with open(self.p_sinfo, "r") as f:
            _info = json.load(f)
        _nuitka_cfg = _info[self.title].get("release_info", {}).get("nuitka", {})
        self.onefile: bool = _nuitka_cfg.get("onefile", False)
        self.extra_nuitka_args: list[str] = _nuitka_cfg.get("extra_args", [])

        # Serializes the .dist → runtime/ merge step inside
        # compile_host so its ``.dist`` doesn't race on shared runtime
        # files (python313.dll, tcl/, ...) if other phases ever ship
        # things into runtime/ concurrently.
        self._merge_lock = threading.Lock()

    def _resolve_release_targets(self) -> list[Screen] | None:
        all_group = self.Groups[Group.ALL]
        # No filter → every releasable screen (tabbed always count;
        # standalones only when release=true).
        if not self.release_groups and not self.release_screens:
            return [s for s in all_group.screenlist if s.tabbed or s.release]

        wanted: set[str] = set()

        for gname in self.release_groups:
            grp = self.Groups.get(gname)
            if grp is None:
                print(f"Release aborted: group '{gname}' does not exist.", flush=True)
                return None
            skipped: list[str] = []
            for scr in grp.screenlist:
                if scr.tabbed or scr.release:
                    wanted.add(scr.name)
                else:
                    skipped.append(scr.name)
            if skipped:
                print(
                    f"Group '{gname}': skipping {len(skipped)} standalone "
                    f"screen(s) marked release=false: {', '.join(skipped)}",
                    flush=True,
                )

        for sname in self.release_screens:
            scr = all_group.get(sname)
            if scr is None:
                print(f"Release aborted: screen '{sname}' does not exist.", flush=True)
                return None
            if not (scr.tabbed or scr.release):
                print(
                    f"Release aborted: screen '{sname}' is marked release=false "
                    f"and cannot be released directly.",
                    flush=True,
                )
                return None
            wanted.add(sname)

        # Preserve project (screenlist) order for deterministic builds.
        targets = [s for s in all_group.screenlist if s.name in wanted]
        if not targets:
            print("Release aborted: no screens to release.", flush=True)
            return None
        return targets

    # ── Nuitka runner ─────────────────────────────────────────────────────────

    _LINE_WIDTH = 70

    def _compiler_args(self) -> list:
        """Return Nuitka compiler-selection flags for the current platform.

        Forces MSVC on Windows so Nuitka does not silently fall back to its
        bundled zig toolchain, which has produced corrupt frozen-bytecode
        binaries on Python 3.13 (see #35).  On Linux and macOS, Nuitka's
        auto-detection picks the platform-native compiler (gcc / clang),
        which is what we want — no flag needed.
        """
        if sys.platform == "win32":
            return ["--msvc=latest"]
        return []

    def _check_compiler(self) -> bool:
        """Verify the platform's required C compiler is installed.

        Aborts ``VIS release`` with an actionable error before any pip
        updates or compilation steps if the compiler we plan to hand to
        Nuitka is missing.  See #35 for why falling back silently is bad.

        Returns ``True`` when the compiler is available, ``False`` (with
        a printed message) otherwise.
        """
        if sys.platform == "win32":
            # Nuitka locates MSVC via vswhere.exe + the registry, NOT $PATH.
            # cl.exe is only on PATH inside a Developer Command Prompt, so
            # we must use the same discovery mechanism Nuitka does.
            vswhere = (
                "C:/Program Files (x86)/Microsoft Visual Studio/"
                "Installer/vswhere.exe"
            )
            if not exists(vswhere):
                self._print_msvc_missing()
                return False
            try:
                result = subprocess.run(
                    [
                        vswhere, "-products", "*",
                        "-requires", "Microsoft.VisualCpp.Tools.HostX64.TargetX64",
                        "-property", "installationPath",
                    ],
                    capture_output=True, text=True, timeout=15,
                )
            except (subprocess.TimeoutExpired, OSError):
                self._print_msvc_missing()
                return False
            if not result.stdout.strip():
                self._print_msvc_missing()
                return False
            return True

        if sys.platform == "linux":
            if shutil.which("gcc") is None:
                print(
                    "\nVIS release requires gcc.\n"
                    "Install via your package manager, e.g.:\n"
                    "    sudo apt install build-essential\n",
                    flush=True,
                )
                return False
            return True

        if sys.platform == "darwin":
            # clang ships with the Xcode Command Line Tools.
            if shutil.which("clang") is None:
                print(
                    "\nVIS release requires clang.\n"
                    "Install the Xcode Command Line Tools:\n"
                    "    xcode-select --install\n",
                    flush=True,
                )
                return False
            return True

        # Unknown platform — let Nuitka try and fail with its own message.
        return True

    def _check_tools(self) -> bool:
        """Verify required Python build tools are installed (#88).

        Replaces the auto-upgrade pass that used to run on every release.
        That pass was the trigger for the zig regression in #35 — a
        Nuitka upgrade silently pulled in a broken toolchain.  Pinning
        the toolchain in ``pyproject.toml`` and just *checking* that the
        pinned tools are present here is the safer move.

        On a missing tool, prints the exact ``pip install`` command the
        user should run and returns ``False``.
        """
        # (module name passed to ``python -m``, pip distribution name)
        tools = [
            ("pip", "pip"),
            ("nuitka", "nuitka"),
            ("PyInstaller", "pyinstaller"),
        ]
        missing = []
        for module_name, install_name in tools:
            try:
                result = subprocess.run(
                    [sys.executable, "-m", module_name, "--version"],
                    capture_output=True, timeout=15,
                )
                if result.returncode != 0:
                    missing.append(install_name)
            except (subprocess.TimeoutExpired, OSError):
                missing.append(install_name)

        if not missing:
            return True

        # pip itself missing — can't pip install pip.  Bootstrap via ensurepip.
        if "pip" in missing:
            print(
                "\nVIS release requires pip but it is not available in this "
                "Python interpreter.\n"
                "Bootstrap it with:\n"
                f"    {sys.executable} -m ensurepip --upgrade\n",
                flush=True,
            )
            return False

        names = ", ".join(missing)
        cmd = f"{sys.executable} -m pip install {' '.join(missing)}"
        print(
            f"\nVIS release requires the following Python package(s): {names}\n"
            f"Install with:\n"
            f"    {cmd}\n",
            flush=True,
        )
        return False

    @staticmethod
    def _print_msvc_missing():
        print(
            "\nVIS release requires Microsoft Visual C++ Build Tools.\n"
            "  1. Download: https://aka.ms/vs/17/release/vs_BuildTools.exe\n"
            "  2. In the installer, select the 'Desktop development with C++'\n"
            "     workload (MSVC v143 + Windows SDK).\n"
            "  3. After installation finishes, open a fresh terminal and\n"
            "     re-run VIS release.\n",
            flush=True,
        )

    def _check_patchelf(self) -> bool:
        """Verify ``patchelf`` is installed when releasing on Linux.

        Nuitka's standalone mode on Linux requires ``patchelf`` to rewrite
        ``RPATH`` / ``RUNPATH`` on every bundled ``.so``.  Without it Nuitka
        aborts mid-build (often after many compilations have already
        finished), so fail fast here with an actionable hint — same
        treatment as the compiler check (#86).

        macOS uses ``install_name_tool`` from the Xcode CLI tools; Windows
        PE binaries import by base name and need nothing analogous.

        Returns ``True`` when the prerequisite is satisfied (or when the
        platform doesn't need it), ``False`` (with a printed message)
        otherwise.
        """
        if sys.platform != "linux":
            return True
        if shutil.which("patchelf") is None:
            print(
                "\nVIS release requires patchelf on Linux.\n"
                "Install via your package manager, e.g.:\n"
                "    sudo apt install patchelf\n",
                flush=True,
            )
            return False
        return True

    def _status(self, text: str, newline: bool = False):
        """Overwrite the single progress line. Pads to _LINE_WIDTH."""
        end = "\n" if newline else ""
        sys.stdout.write(f"\r{text:<{self._LINE_WIDTH}}{end}")
        sys.stdout.flush()

    def _run_nuitka_silent(self, parts: list, cwd: str) -> tuple[bool, str]:
        """Run a Nuitka command, draining output without printing progress.

        Returns ``(ok, last_error)``.  ``last_error`` is the most recent
        FATAL or ``error:`` line (truncated by callers as needed) — empty
        string when the build succeeded.
        """
        proc = subprocess.Popen(
            parts, cwd=cwd,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, errors="replace",
        )
        last_error = ""
        for raw in proc.stdout:
            for segment in raw.replace('\r', '\n').split('\n'):
                segment = segment.strip()
                if not segment:
                    continue
                if 'FATAL' in segment or 'error:' in segment.lower():
                    last_error = segment
        proc.wait()
        return proc.returncode == 0, last_error

    def _run_nuitka(self, parts: list, name: str, cwd: str) -> bool:
        """Run a Nuitka command, showing progress on a single overwritten line.

        Returns True on success, False on failure.
        """
        self._cat_index += 1
        self._step += 1
        prefix = f"  [{self._step}/{self._total_steps}] {self._category} {self._cat_index}/{self._cat_count} - {name}"
        self._status(prefix + " ...")

        start = time.monotonic()
        proc = subprocess.Popen(
            parts, cwd=cwd,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, errors="replace",
        )

        last_error = ""
        for raw in proc.stdout:
            for segment in raw.replace('\r', '\n').split('\n'):
                segment = segment.strip()
                if not segment:
                    continue
                # C file compilation progress — Nuitka emits variants like
                # "Compiled 23/47", "Compiled 23 of 47", or
                # "Compiled 23 out of 47" depending on version.
                m = _re.search(r'Compiled (\d+)\s*(?:/|of|out of)\s*(\d+)', segment)
                if m:
                    self._status(f"{prefix} — C {m.group(1)}/{m.group(2)}")
                    continue
                if 'Backend C linking' in segment:
                    self._status(f"{prefix} — linking")
                    continue
                # Analysis / optimization phase — long-running silent
                # gaps before the C compile, where progress otherwise
                # appears stuck on "...".
                if 'Optimizing modules' in segment or 'Doing module' in segment:
                    self._status(f"{prefix} — analyzing")
                    continue
                # Capture last FATAL/error line for failure reporting
                if 'FATAL' in segment or 'error:' in segment.lower():
                    last_error = segment

        proc.wait()
        elapsed = time.monotonic() - start
        if proc.returncode != 0:
            # Print failure on its own line so it stays visible
            msg = f"{prefix} FAILED"
            if last_error:
                msg += f" — {last_error[:60]}"
            self._status(msg, newline=True)
            return False
        # Emit a permanent per-binary line so successive binaries don't
        # overwrite each other on a single \r-terminated row (#136).
        self._status(f"{prefix} done ({elapsed:.1f}s)", newline=True)
        return True

    def compile_host(self) -> tuple[bool, str]:
        """Compile the Host as a Nuitka executable.

        Standalone mode produces a ``.dist`` folder which is merged into
        ``self.final``.  Onefile mode produces a single self-contained
        ``.exe`` which is moved to ``self.final``.  In onefile mode the
        entry script is wrapped with a sys.path bootstrap so external
        compile targets resolve from the install root (see
        :meth:`_make_bootstrap_wrapper`).

        Uses ``_run_nuitka`` (live progress) since the Host is now the
        only binary in a build — under the always-Host model there are
        no per-screen .exes competing for the progress line.  The .dist
        → runtime/ merge is wrapped in ``self._merge_lock`` for safety
        if any other phase ever races on runtime files.  Returns
        ``(ok, err)`` — err is always empty on this path because
        ``_run_nuitka`` prints failure details itself before returning.
        """
        ixt = ".ico" if sys.platform == "win32" else ".xbm"
        icon_file = f"{self.p_project}/Icons/{self.d_icon}{ixt}"

        mode = "--onefile" if self.onefile else "--standalone"

        parts = [sys.executable, "-m", "nuitka", mode]
        parts.extend(self._compiler_args())
        parts.append("--follow-imports")
        parts.append("--enable-plugin=tk-inter")

        # The tk-inter plugin handles Tcl/Tk runtime data files but only
        # auto-bundles the tkinter Python package's actively-imported
        # submodules.  Force the whole package in so shared .pyds (which
        # exclude tkinter from their own bundle) can reach every submodule.
        parts.append("--include-package=tkinter")

        # Dotted hidden_imports (e.g. ``PIL._tkinter_finder``) are
        # module-level hints — keep them as ``--include-module``.
        # Top-level shared packages, Screens, and modules sub-packages
        # are all external compile targets and get blanket nofollow via
        # _nofollow_flags() below.
        for imp in self.hidden_imports:
            if "." in imp:
                parts.append(f"--include-module={imp}")

        parts.extend(self._nofollow_flags())
        # Bundle full stdlib so any shared .pyd loaded at runtime by
        # this Host .exe can reach stdlib (asyncio, logging,
        # multiprocessing, socket, _overlapped, ...) via the frozen
        # host's import system.  See _stdlib_includes() docstring.
        parts.extend(self._stdlib_includes())

        if icon_file and exists(icon_file):
            parts.append(f"--windows-icon-from-ico={icon_file}")

        if self.company:
            parts.append(f"--windows-company-name={self.company}")
            parts.append(f"--windows-product-name={self.title}")
            year = datetime.datetime.now().year
            parts.append(f"--windows-file-description={self.title}")
            parts.append(f"--copyright=Copyright {year} {self.company}")

        parts.append(f"--windows-product-version={self.Version}")
        parts.append(f"--output-dir={self.build_dir}")
        parts.append(f"--output-filename={self.title}{_EXE_EXT}")

        # TEMP DEBUG: console disabled so startup errors are visible.
        # Revert before shipping.
        # if sys.platform == "win32":
        #     parts.append("--windows-console-mode=disable")

        parts.append("--assume-yes-for-downloads")
        parts.extend(self.extra_nuitka_args)

        entry_script = self._entry_for_compile(self.host_script)
        parts.append(entry_script)

        if not self._run_nuitka(parts, self.title, self.p_project):
            return False, ""  # _run_nuitka already printed the failure line

        with self._merge_lock:
            if not self._place_exe_output(entry_script, self.title):
                return False, "merge into runtime/ failed"
        return True, ""

    def _place_exe_output(self, entry_script: str, exe_basename: str) -> bool:
        """Move/merge a Nuitka build's output into ``self.final``.

        Onefile mode produces ``<build_dir>/<exe_basename>.exe`` directly
        — just move it.  Standalone mode produces a ``<stem>.dist/``
        folder (where stem is the entry script's basename minus
        extension); the .dist contents are merged into ``self.final``,
        with host-style overwrite semantics (host runtime wins).
        """
        if self.onefile:
            produced = f"{self.build_dir}{exe_basename}{_EXE_EXT}"
            if not exists(produced):
                self._status(
                    f"  Onefile build produced no exe at {produced}",
                    newline=True,
                )
                return False
            os.makedirs(self.runtime, exist_ok=True)
            target = os.path.join(self.runtime, f"{exe_basename}{_EXE_EXT}")
            if exists(target):
                os.remove(target)
            shutil.move(produced, target)
            return True

        stem = os.path.splitext(os.path.basename(entry_script))[0]
        nuitka_dist = f"{self.build_dir}{stem}.dist"
        _skip = {'.build', '_internal', '__pycache__'}
        if exists(nuitka_dist):
            # No rmtree, no rename: preserve <stem>.dist/ in build_dir
            # for debugging and byte-comparison audits between Host and
            # screen builds.  Subsequent builds overwrite their own
            # .dist/ in place; adds a ~80 MB/screen fixed footprint to
            # build_dir, doesn't accumulate.
            os.makedirs(self.runtime, exist_ok=True)
            for dirpath, dirs, files in os.walk(nuitka_dist):
                dirs[:] = [d for d in dirs if d not in _skip and not d.endswith('.build')]
                rel = os.path.relpath(dirpath, nuitka_dist)
                dest = os.path.join(self.runtime, rel)
                os.makedirs(dest, exist_ok=True)
                for f in files:
                    src = os.path.join(dirpath, f)
                    shutil.copy2(src, os.path.join(dest, f))
        return True

    def compile_screens(self, mode="all"):
        """Compile each screen's wrapper .pyd and (optionally) the Host .exe.

        For every screen in ``release_targets`` a single wrapper ``.pyd``
        is produced at ``runtime/<stem>.pyd``.  The wrapper bundles
        marshalled bytecode for the entry script and every ``f_*`` /
        ``j_*`` / ``m_*`` source file; per-tab namespaces are built from
        that dict at runtime by ``TabManager._build_namespace``.  No
        separate ``Screens/<name>.pyd`` or ``modules/<name>.pyd``
        artifacts ship.

        ``mode`` filters which compilations to run: ``"pyd"`` for screen
        wrappers, ``"exe"`` for the Host binary, or ``"all"`` for both
        (default).  Under the always-Host model there are no per-screen
        .exes — every screen opens through the Host (as a tab or a
        chromeless DetachedWindow); the Host binary is the only .exe
        in the install.
        """
        if mode in ("all", "pyd"):
            # Wrapper .pyd is built for every release target — tabbed and
            # standalone alike — so the Host can open any of them as a
            # tab through TabManager._build_namespace.
            screens = list(self.release_targets)
            if screens:
                if not self._compile_pyds_parallel(screens):
                    return False

        if mode in ("all", "exe"):
            # compile_host now uses _run_nuitka (live progress) and
            # manages its own step/cat_index bookkeeping — no need to
            # increment here.  Failure detail is printed by _run_nuitka.
            ok, _err = self.compile_host()
            if not ok:
                return False

        return True

    def _modules_for_release(self) -> list[tuple[str, str]]:
        """Return ``[(screen_name, modules_subdir_path), ...]`` for every
        release-targeted screen that has a ``modules/<screen>/`` package.

        Screens without a corresponding modules directory contribute
        nothing (they have no per-screen logic to ship externally).
        """
        modules_root = os.path.join(self.p_project, "modules")
        if not os.path.isdir(modules_root):
            return []
        out: list[tuple[str, str]] = []
        for scr in self.release_targets:
            path = os.path.join(modules_root, scr.name)
            if os.path.isdir(path):
                out.append((scr.name, path))
        return out

    def _screens_for_release(self) -> list[tuple[str, str]]:
        """Return ``[(screen_name, screens_subdir_path), ...]`` for every
        release-targeted screen that has a ``Screens/<screen>/`` UI
        sub-package holding f_* section files.  Screens without one
        (single-file lrfEditor-style screens) contribute nothing.
        """
        screens_root = os.path.join(self.p_project, "Screens")
        if not os.path.isdir(screens_root):
            return []
        out: list[tuple[str, str]] = []
        for scr in self.release_targets:
            path = os.path.join(screens_root, scr.name)
            if os.path.isdir(path):
                out.append((scr.name, path))
        return out

    # ── Onefile bootstrap injection ───────────────────────────────────────

    _BOOTSTRAP_BANNER = (
        "# AUTO-GENERATED by VIS release.  Prepended to entry scripts in\n"
        "# onefile mode so external Screens/, modules/, and shared\n"
        "# package .pyd files resolve at runtime.  Python in onefile\n"
        "# runs from a temp unpack dir, not the install root, so the\n"
        "# install root must be added to sys.path explicitly.\n"
        "import sys as _vis_sys, os as _vis_os\n"
        "_vis_install_dir = _vis_os.path.dirname(_vis_sys.executable)\n"
        "if _vis_install_dir not in _vis_sys.path:\n"
        "    _vis_sys.path.insert(0, _vis_install_dir)\n"
        "del _vis_sys, _vis_os, _vis_install_dir\n"
        "\n"
    )

    def _make_bootstrap_wrapper(self, script_path: str) -> str:
        """Write a wrapper script that prepends the install-root sys.path
        bootstrap to ``script_path`` and return the wrapper's path.

        Used only for onefile builds.  The wrapper lives inside
        ``self.build_dir`` so it gets picked up by Nuitka at compile
        time without touching the user's source files.
        """
        os.makedirs(self.build_dir, exist_ok=True)
        stem = os.path.splitext(os.path.basename(script_path))[0]
        wrapper_path = f"{self.build_dir}{stem}_bootstrap.py"
        with open(script_path, "r", encoding="utf-8") as f:
            original = f.read()
        with open(wrapper_path, "w", encoding="utf-8") as f:
            f.write(self._BOOTSTRAP_BANNER + original)
        return wrapper_path

    def _entry_for_compile(self, script_path: str) -> str:
        """Return the script path Nuitka should compile.

        For standalone builds the install root is already on sys.path
        (Python runs from there), so the original script works as-is.
        For onefile builds we emit a bootstrap wrapper that prepends the
        sys.path setup.
        """
        if self.onefile:
            return self._make_bootstrap_wrapper(script_path)
        return script_path

    def _compile_targets(self) -> list[str]:
        """Every external compile target this release will produce.

        Used by each phase to construct ``--nofollow-import-to`` flags
        for every target except the one *this* compile is building.  The
        universal rule: every member must be either ``--include-package``
        (or an entry script) or ``--nofollow-import-to`` for every
        Nuitka invocation — never both, never neither.

        Members:
          * Every shared package (``compile_shared`` ships these)
          * ``Screens`` — every tabbed screen .pyd lands under here
          * ``modules`` — every per-screen modules .pyd lands under here
        """
        targets = list(self.shared_pkg_names)
        targets.append("Screens")
        targets.append("modules")
        # Per-screen dotted entries so entry .exe compiles (which call
        # _nofollow_flags() without exclude_self) don't freeze a stub
        # ``Screens.<name>`` or ``modules.<name>`` package alongside
        # the on-disk ``.pyd``.  An entry script's
        # ``import Screens.<name>.f_xxx`` otherwise causes Nuitka
        # to bundle just the subpackage's ``__init__.py`` reference,
        # which shadows the real on-disk ``.pyd`` at runtime and
        # produces an ImportError on the f_*/m_* submodule lookup.
        for name, _path in self._screens_for_release():
            targets.append(f"Screens.{name}")
        for name, _path in self._modules_for_release():
            targets.append(f"modules.{name}")
        return targets

    # Runtime-only filter: distribution names of build/dev tools we
    # never want to bundle into a shipped .pyd.  Normalized to lower-case
    # with dashes (PEP 503-ish).
    _BUILDTIME_DEPS = frozenset({
        "pyinstaller", "pyinstaller-hooks-contrib",
        "nuitka",
        "pip", "setuptools", "wheel", "build",
    })

    # Stdlib top-level modules that Nuitka's --module mode shouldn't
    # be told to follow.  Everything else from sys.stdlib_module_names
    # gets passed as --follow-import-to to shared .pyd compiles so any
    # stdlib transitively used by bundled third-party deps is bundled
    # alongside them.
    #
    # - tkinter / _tkinter / idlelib / turtle*: handled by the
    #   tk-inter Nuitka plugin in entry-script compiles; double-
    #   handling at the .pyd level conflicts with the plugin.
    # - antigravity, this: easter eggs, never useful.
    # - __main__ / __hello__ / __phello__: special entries.
    # - test / unittest / doctest: test infrastructure, ships its own
    #   data files Nuitka can't always locate.
    _STDLIB_HINT_EXCLUDE = frozenset({
        "tkinter", "_tkinter", "idlelib", "turtle", "turtledemo",
        "antigravity", "this",
        "__main__", "__hello__", "__phello__",
        "test", "unittest", "doctest",
    })

    def _stdlib_hints_for_shared(self) -> list[str]:
        """Every top-level stdlib module Nuitka should bundle into the
        entry-script .exes so any shared .pyd loaded at runtime can
        reach stdlib via the frozen host's import system.

        Uses :data:`sys.stdlib_module_names` (Python 3.10+) so the list
        adapts to whichever Python version is running the release —
        when the user upgrades Python and a new stdlib module appears,
        it shows up here automatically.

        Filters out ``_STDLIB_HINT_EXCLUDE``.

        Note: ``--follow-import-to`` of stdlib names is a no-op for
        Nuitka ``--module`` mode — it silently doesn't bundle the
        stdlib module into the .pyd.  The same names DO get bundled
        when passed as ``--include-module`` / ``--include-package`` to
        a ``--standalone`` build, so we apply them to the entry-script
        compiles (Host + standalone screens) instead.  Shared .pyds
        loaded by those .exes resolve stdlib through the host runtime.
        """
        return sorted(m for m in sys.stdlib_module_names
                      if m not in self._STDLIB_HINT_EXCLUDE)

    def _stdlib_includes(self) -> list[str]:
        """Build the list of ``--include-module=<name>`` /
        ``--include-package=<name>`` flags for stdlib bundling into an
        entry-script (--standalone) compile.

        Detects packages vs single-file modules using
        :func:`importlib.util.find_spec` — packages get
        ``--include-package`` so all their submodules ship (e.g. asyncio
        needs windows_events which pulls _overlapped), single modules
        get ``--include-module``.  Names that fail to resolve in the
        current Python (e.g. platform-specific stdlib that's absent on
        this OS) are skipped silently.
        """
        import importlib.util
        flags: list[str] = []
        for name in self._stdlib_hints_for_shared():
            try:
                spec = importlib.util.find_spec(name)
            except (ImportError, ValueError, AttributeError):
                continue
            if spec is None:
                continue
            if spec.submodule_search_locations is not None:
                flags.append(f"--include-package={name}")
            else:
                flags.append(f"--include-module={name}")
        return flags

    def _dist_to_top_levels(self, dist_name: str) -> list[str]:
        """Map a pip distribution name to its importable top-level name(s).

        Prefers ``top_level.txt`` (present on most installed dists).  Falls
        back to scanning ``dist.files`` for top-level packages.  Returns
        ``[]`` if the distribution isn't installed.
        """
        try:
            dist = importlib.metadata.distribution(dist_name)
        except importlib.metadata.PackageNotFoundError:
            return []
        top_text = dist.read_text("top_level.txt")
        if top_text:
            return [ln.strip() for ln in top_text.splitlines() if ln.strip()]
        names: set[str] = set()
        for f in (dist.files or []):
            head = str(f).replace("\\", "/").split("/", 1)[0]
            if head.endswith(".dist-info") or head.endswith(".egg-info"):
                continue
            if head.endswith(".py") and "/" not in head:
                names.add(head[:-3])           # single-file module
            elif "." not in head:
                names.add(head)                # package directory
        return sorted(names)

    def _resolve_runtime_deps(self, pkg: str) -> list[str]:
        """Walk ``pkg``'s transitive runtime dep graph via pip metadata
        and return unique top-level import names to bundle into
        ``<pkg>.pyd``.

        Skips build-tool deps (pyinstaller, nuitka, pip, etc.) and
        optional/extras deps (those gated on ``extra == 'foo'`` markers).
        Resolved entirely at release-run time, so it adapts to whatever
        the project has installed in its build env — a project that adds
        a new package to its install will pick up that package's deps
        automatically on the next release without changes here.
        """
        seen_dists: set[str] = {pkg.lower().replace("_", "-")}
        top_levels: list[str] = []
        seen_tops: set[str] = set()
        queue: list[str] = [pkg]
        while queue:
            current = queue.pop(0)
            try:
                dist = importlib.metadata.distribution(current)
            except importlib.metadata.PackageNotFoundError:
                continue
            for req in (dist.requires or []):
                # "notify-py" / "loguru (>=0.5)" / "foo; extra == 'docs'"
                head, _, marker = req.partition(";")
                if "extra ==" in marker:
                    continue   # extras-only dep; not a runtime requirement
                dep_name = head.split("[")[0].split("(")[0].split()[0].strip()
                if not dep_name:
                    continue
                norm = dep_name.lower().replace("_", "-")
                if norm in seen_dists or norm in self._BUILDTIME_DEPS:
                    continue
                seen_dists.add(norm)
                queue.append(dep_name)
                for top in self._dist_to_top_levels(dep_name):
                    if top not in seen_tops:
                        seen_tops.add(top)
                        top_levels.append(top)
        return top_levels

    def _nofollow_flags(
        self,
        exclude_self: str | set[str] | None = None,
    ) -> list[str]:
        """Build ``--nofollow-import-to=X`` for every compile target,
        skipping any name in ``exclude_self`` (the thing(s) this compile
        is building or wants to follow itself).

        Accepts either a single string or a set/iterable of strings so
        a single build can exempt multiple targets — e.g. a standalone
        screen .exe needs to follow both its own ``Screens.<name>`` and
        ``modules.<name>`` so they get bundled with all their f_*/m_*
        submodules, while still nofollowing every other screen.

        Also adds ``--no-deployment-flag=excluded-module-usage``: by
        default Nuitka treats any runtime ``import`` of a module that
        was nofollow'd as an error at startup ("Module 'X' was actively
        excluded from Nuitka compilation").  Our architecture
        deliberately ships those modules as external ``.pyd`` files
        next to the .exe and imports them at runtime — that's the whole
        point of the multi-target build.  Disabling this deployment
        flag tells Nuitka to allow the runtime import (#105).
        """
        if exclude_self is None:
            excludes: set[str] = set()
        elif isinstance(exclude_self, str):
            excludes = {exclude_self}
        else:
            excludes = set(exclude_self)
        out: list[str] = []
        for t in self._compile_targets():
            if t not in excludes:
                out.append(f"--nofollow-import-to={t}")
        if out:
            out.append("--no-deployment-flag=excluded-module-usage")
        return out

    def _build_screen_wrapper(self, scr) -> str:
        """Generate the per-screen wrapper ``.py`` source and return its path.

        The wrapper contains a single ``_EMBEDDED`` dict holding marshalled
        bytecode for the screen's entry script and every ``f_*`` / ``j_*``
        in ``Screens/<name>/`` plus every ``m_*`` in ``modules/<name>/``.
        At runtime ``TabManager._load_codes_from_embedded`` reads this
        dict and unmarshals into code objects for per-tab exec.

        Wrapper file is named ``<stem>.py`` (where ``stem`` is the entry
        script's basename without extension) so the Nuitka-compiled
        ``.pyd`` exports ``PyInit_<stem>`` — what Python looks for when
        the runtime does ``importlib.import_module(stem)``.  It lives
        under ``self.build_dir/wrappers/`` to avoid colliding with
        anything Nuitka writes at the build_dir root.
        """
        stem = os.path.splitext(scr.script)[0]
        embedded: dict = {"entry": None, "screens": {}, "modules": {}}

        # Entry script
        with open(scr.script_path, "rb") as f:
            entry_src = f.read()
        embedded["entry"] = marshal.dumps(compile(entry_src, scr.script, "exec"))

        # Screens/<name>/f_*, j_*
        if os.path.isdir(scr.path):
            for fname in sorted(os.listdir(scr.path)):
                if not fname.endswith(".py") or fname == "__init__.py":
                    continue
                full = os.path.join(scr.path, fname)
                with open(full, "rb") as f:
                    src = f.read()
                embedded["screens"][fname[:-3]] = marshal.dumps(compile(src, full, "exec"))

        # modules/<name>/m_*
        if os.path.isdir(scr.m_path):
            for fname in sorted(os.listdir(scr.m_path)):
                if not fname.endswith(".py") or fname == "__init__.py":
                    continue
                full = os.path.join(scr.m_path, fname)
                with open(full, "rb") as f:
                    src = f.read()
                embedded["modules"][fname[:-3]] = marshal.dumps(compile(src, full, "exec"))

        # Per-screen subdir so multiple screens with name collisions
        # (impossible today but cheap insurance) don't stomp each other.
        wrapper_dir = os.path.join(self.build_dir, "wrappers", stem)
        os.makedirs(wrapper_dir, exist_ok=True)
        wrapper_path = os.path.join(wrapper_dir, f"{stem}.py")
        wrapper_src = (
            f'"""Per-screen bundle for {scr.name!r} — VIS release artifact.\n'
            f"\n"
            f"Loaded by VIStk.Objects._TabManager when the Host opens this\n"
            f"screen.  Contains marshalled bytecode for the entry script and\n"
            f"every f_*, j_*, and m_* file; per-tab namespaces are built\n"
            f"from this dict at runtime.\n"
            f'"""\n'
            f"\n"
            f"_EMBEDDED = {embedded!r}\n"
        )
        with open(wrapper_path, "w", encoding="utf-8") as f:
            f.write(wrapper_src)
        return wrapper_path

    def _compile_screen_pyd(self, scr) -> tuple[bool, str]:
        """Compile one screen → ``runtime/<stem>.pyd``.

        Builds a wrapper ``.py`` containing marshalled bytecode for the
        entry script and every ``f_*`` / ``j_*`` / ``m_*`` source file,
        then Nuitka-compiles that wrapper with ``--module``.  At runtime
        ``TabManager._build_namespace`` imports this .pyd, reads its
        ``_EMBEDDED`` dict, and exec's the bytecode into per-tab
        namespaces — no separate ``Screens/<name>.pyd`` or
        ``modules/<name>.pyd`` artifacts are produced.

        The wrapper has no runtime imports beyond the standard library,
        so the previous ``--include-package`` + ``--nofollow-import-to``
        dance falls away.

        Wrapper file is named ``<stem>.py`` (matching the entry script
        stem) so the produced .pyd exports ``PyInit_<stem>`` — required
        for ``importlib.import_module(stem)`` at runtime to succeed.
        Each screen's wrapper + output live in their own subdir under
        ``build_dir/wrappers/<stem>/`` so concurrent compiles don't
        race on shared output paths.

        Threadsafe — uses :meth:`_run_nuitka_silent` so concurrent calls
        don't fight over the progress display.  Returns ``(ok, error)``.
        """
        stem = os.path.splitext(scr.script)[0]
        wrapper_path = self._build_screen_wrapper(scr)
        wrapper_dir = os.path.dirname(wrapper_path)

        parts = [
            sys.executable, "-m", "nuitka", "--module",
            *self._compiler_args(),
            f"--output-dir={wrapper_dir}",
            "--assume-yes-for-downloads",
            *self._nofollow_flags(),
            wrapper_path,
        ]

        ok, err = self._run_nuitka_silent(parts, wrapper_dir)
        if not ok:
            return False, err or "nuitka returned non-zero"

        # Output is in the wrapper's isolated subdir.  May be plain
        # ``<stem>.pyd`` or ABI-tagged like ``<stem>.cp313-win_amd64.pyd``
        # depending on Nuitka config.  Either way, move it to the
        # runtime root as ``<stem>.pyd``.
        built = glob.glob(f"{wrapper_dir}/{stem}*{_MOD_EXT}")
        if not built:
            return False, f"no {_MOD_EXT} produced at {wrapper_dir}/{stem}*{_MOD_EXT}"
        target = f"{self.runtime}/{stem}{_MOD_EXT}"
        if os.path.exists(target):
            os.remove(target)
        # If Nuitka emitted multiple variants (rare), prefer the exact
        # stem match.
        primary = next(
            (bp for bp in built if os.path.basename(bp) == f"{stem}{_MOD_EXT}"),
            built[0],
        )
        shutil.move(primary, target)
        return True, ""

    def _run_parallel(self, jobs: list, label: str, max_workers: int) -> bool:
        """Run a list of compile jobs concurrently with shared progress.

        ``jobs`` is a list of ``(name, fn)`` tuples where ``fn()`` returns
        ``(ok: bool, error: str)``.  ``label`` is the singular noun used
        in the progress banner ("screen", "package", ...).

        Returns ``True`` iff every job succeeded.  On the first failure,
        queued-but-unstarted jobs are cancelled — already-running ones
        continue (Python threads can't be killed), so the ``build_dir``
        state stays consistent on exit.
        """
        n = len(jobs)
        print(f"  Compiling {n} {label}(s) in parallel ({max_workers} workers)...",
              flush=True)

        lock = threading.Lock()
        starts: dict[str, float] = {}

        def worker(name, fn):
            with lock:
                starts[name] = time.monotonic()
            ok, err = fn()
            return name, ok, err

        all_ok = True
        cancel_pending = False
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = [pool.submit(worker, name, fn) for name, fn in jobs]
            for fut in as_completed(futures):
                if fut.cancelled():
                    continue
                name, ok, err = fut.result()
                with lock:
                    self._step += 1
                    self._cat_index += 1
                    elapsed = time.monotonic() - starts.get(name, time.monotonic())
                    tag = (f"  [{self._step}/{self._total_steps}] {self._category} "
                           f"{self._cat_index}/{self._cat_count} - {name}")
                    if ok:
                        print(f"{tag} done ({elapsed:.1f}s)", flush=True)
                    else:
                        print(f"{tag} FAILED — {err[:80]}", flush=True)
                        all_ok = False
                        if not cancel_pending:
                            cancel_pending = True
                            for f in futures:
                                f.cancel()
        return all_ok

    def _compile_pyds_parallel(self, screens: list) -> bool:
        """Compile every tabbed screen's wrapper .pyd concurrently.

        Each screen produces ONE wrapper .pyd at ``runtime/<stem>.pyd``
        containing marshalled bytecode for the entry script and every
        ``f_*`` / ``j_*`` / ``m_*`` source file — no separate
        ``Screens/<name>.pyd`` or ``modules/<name>.pyd`` artifacts.

        Workers default to ``cpu_count // 2`` to leave headroom for
        Nuitka's per-process C compiler subprocesses.
        """
        max_workers = max(1, (os.cpu_count() or 4) // 2)
        jobs = [(s.name, lambda s=s: self._compile_screen_pyd(s)) for s in screens]
        return self._run_parallel(jobs, "screen", max_workers)

    def _compile_shared_parallel(self, packages: list) -> bool:
        """Compile shared packages concurrently.

        ``packages`` is a list of ``(pkg_name, pkg_path)`` tuples.
        Capped at 3 workers — each shared package compile is heavyweight
        (whole submodule tree under ``--include-package``) and we share
        the host with the screens phase that follows.
        """
        max_workers = min(3, max(1, len(packages)))
        jobs = [(name, lambda n=name, p=path: self._compile_one_shared(n, p))
                for name, path in packages]
        return self._run_parallel(jobs, "package", max_workers)

    def _compile_one_shared(self, pkg: str, pkg_path: str) -> tuple[bool, str]:
        """Compile one shared package → ``final/<pkg>.pyd``.

        The output lives at the install root (alongside ``python3xx.dll``)
        so Python's default ``sys.path`` resolves ``import <pkg>`` to this
        file at runtime — no path injection needed in entry scripts.

        Peer shared packages (everything else in ``shared_pkg_names``) are
        excluded with ``--nofollow-import-to`` so this build doesn't end
        up containing a copy of, say, VIStk inside pywomlib.pyd.

        Threadsafe — uses :meth:`_run_nuitka_silent`.
        """
        # Nuitka's --module mode rejects --follow-imports (the "follow
        # everything" flag) and requires selective follow via
        # --follow-import-to=<name>.  Resolve the package's transitive
        # runtime dep graph via pip metadata and emit one
        # --follow-import-to per top-level import name so deps like
        # notifypy + loguru (for VIStk) or platformdirs (for pywomlib)
        # get bundled into <pkg>.pyd.  Without this, the running .exe
        # imports VIStk.pyd which then tries to import notifypy from a
        # sys.path that doesn't have it, and dies at startup with
        # ModuleNotFoundError.
        runtime_deps = self._resolve_runtime_deps(pkg)
        follow_flags = [f"--follow-import-to={d}" for d in runtime_deps]
        # Stdlib transitively used by bundled deps (logging, asyncio,
        # multiprocessing, etc.) is NOT bundled here — Nuitka --module
        # silently skips stdlib for --follow-import-to.  It IS bundled
        # into the entry-script .exes via _stdlib_includes(), so when
        # this shared .pyd is loaded by a .exe at runtime, stdlib
        # resolves through the .exe's frozen host.

        parts = [
            sys.executable, "-m", "nuitka", "--module",
            *self._compiler_args(),
            # See compile_shared() for why --include-package is required.
            f"--include-package={pkg}",
            f"--output-dir={self.build_dir}",
            "--assume-yes-for-downloads",
            *follow_flags,
            # Self gets --include-package; every other compile target
            # gets --nofollow-import-to.
            *self._nofollow_flags(exclude_self=pkg),
            pkg_path,
        ]

        ok, err = self._run_nuitka_silent(parts, self.p_project)
        if not ok:
            return False, err or "nuitka returned non-zero"

        built = glob.glob(f"{self.build_dir}{pkg}*{_MOD_EXT}")
        if not built:
            return False, f"no {_MOD_EXT} produced at {self.build_dir}{pkg}*{_MOD_EXT}"
        for bp in built:
            shutil.move(bp, f"{self.runtime}/{pkg}{_MOD_EXT}")
        return True, ""

    # NOTE (0.5.X+): Standalone per-screen .exes are gone.  Every
    # installed project ships exactly one binary — the Host .exe —
    # and every screen (tabbed or formerly-standalone) loads through
    # the Host as either a regular tab or a chromeless DetachedWindow.
    # Direct-launch by the user happens via Start Menu shortcuts that
    # invoke ``<project>.exe <ScreenName>`` (Host honors the screen
    # name as a startup argument).  The ``release`` field on Screen no
    # longer triggers an .exe build; it gates Start Menu shortcut
    # creation in the installer instead.

    @staticmethod
    def _has_binary_extensions(pkg_dir: str) -> bool:
        """True if the installed package contains compiled extensions
        (.pyd/.so).  Such packages can't be packed into a single Nuitka
        ``--module`` output — the C extensions are separate binaries
        that must land next to the Python source on disk.  We copy the
        whole package directory into runtime/ instead."""
        for _root, _dirs, files in os.walk(pkg_dir):
            for f in files:
                if f.endswith((".pyd", ".so")):
                    return True
        return False

    def compile_shared(self):
        """Ship shared packages into ``runtime/`` for every .exe to import.

        Each package gets one of two treatments based on whether its
        installed directory contains any compiled extensions:

        * **Pure-Python** → Nuitka ``--module`` into a single
          ``<pkg>.pyd`` at the runtime root.
        * **Has binary extensions (.pyd/.so)** → installed package
          directory copied as-is into ``runtime/<pkg>/``, then every
          ``.py`` in the copy is compiled to a sibling ``.pyc`` and the
          source removed.  Python's ``SourcelessFileLoader`` handles
          ``.pyc``-only modules directly; the original C extensions
          stay untouched alongside.
        """
        # Top-level packages from hidden_imports (no dots = full package)
        packages = [imp for imp in self.hidden_imports if "." not in imp]
        # Plus anything in collect_packages
        for pkg in self.collect_packages:
            if pkg not in packages:
                packages.append(pkg)

        if not packages:
            return True

        # Resolve installed paths up-front so import failures surface in
        # one clear pre-pass instead of getting interleaved with parallel
        # progress output.  Without --include-package, --module mode only
        # compiles the package's __init__.py and silently drops every
        # submodule from the resulting .pyd — see _compile_one_shared.
        resolved: list[tuple[str, str]] = []
        for pkg in packages:
            try:
                mod = __import__(pkg)
                resolved.append((pkg, os.path.dirname(mod.__file__)))
            except Exception:
                print(f"  Skipping {pkg} — not importable", flush=True)

        if not resolved:
            return True

        os.makedirs(self.runtime, exist_ok=True)

        # Split: directory-shipped (binary extensions) vs compile-to-pyd.
        dir_shipped: list[tuple[str, str]] = []
        to_compile: list[tuple[str, str]] = []
        for pkg, pkg_dir in resolved:
            if self._has_binary_extensions(pkg_dir):
                dir_shipped.append((pkg, pkg_dir))
            else:
                to_compile.append((pkg, pkg_dir))

        for pkg, pkg_dir in dir_shipped:
            self._step += 1
            self._cat_index += 1
            prefix = (f"  [{self._step}/{self._total_steps}] "
                      f"{self._category} {self._cat_index}/{self._cat_count} - {pkg}")
            dest = os.path.join(self.runtime, pkg)
            if os.path.exists(dest):
                shutil.rmtree(dest)
            shutil.copytree(
                pkg_dir, dest,
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"),
            )
            import py_compile
            for walk_root, _walk_dirs, walk_files in os.walk(dest):
                for f in walk_files:
                    if not f.endswith(".py"):
                        continue
                    py = os.path.join(walk_root, f)
                    py_compile.compile(py, cfile=py + "c", doraise=True)
                    os.remove(py)
            print(f"{prefix} copied (binary extensions, .py→.pyc)", flush=True)

        if not to_compile:
            return True
        return self._compile_shared_parallel(to_compile)

    def clean(self):
        """Appends project data to dist folder.

        Copies Images, .VIS/project.json, and writes an installed
        project.json with rewritten screen script paths.  Removes any
        stray Nuitka ``.build`` directories from the output.
        """
        print("Appending Screen Data To Environment", flush=True)

        out_dir = self.final

        # Copy Images into runtime/ (alongside the .exes that consume them)
        src = f"{self.p_project}/Images/"
        if exists(src):
            shutil.copytree(src, f"{self.runtime}/Images/", dirs_exist_ok=True)

        # Copy Icons into runtime/
        src = f"{self.p_project}/Icons/"
        if exists(src):
            shutil.copytree(src, f"{self.runtime}/Icons/", dirs_exist_ok=True)

        # Ship top-level framework support files in Screens/ and modules/
        # as .pyc.  Per-screen subdirectories (Screens/AssetManager/,
        # modules/FloorView/, ...) are already compiled into the per-screen
        # .pyds; only loose .py files at the package root need separate
        # handling.  Without this, the entry .exes (which nofollow both
        # `Screens` and `modules` so they resolve from disk) can't find
        # framework imports like `from Screens.root import root, frame`
        # or `from modules.menu import shared_menu_structure`.
        import py_compile
        for subdir in ("Screens", "modules"):
            src = os.path.join(self.p_project, subdir)
            if not os.path.isdir(src):
                continue
            dest = os.path.join(self.runtime, subdir)
            os.makedirs(dest, exist_ok=True)
            for entry in os.listdir(src):
                full_src = os.path.join(src, entry)
                if not os.path.isfile(full_src) or not entry.endswith(".py"):
                    continue
                py_compile.compile(
                    full_src, cfile=os.path.join(dest, entry + "c"),
                    doraise=True,
                )

        # Copy license file if present.  Stays at the install root (NOT in
        # runtime/) so it's the first thing a user sees when they open
        # the install folder.
        for name in ("LICENSE", "LICENSE.txt", "EULA.txt", "EULA.md"):
            src = f"{self.p_project}/{name}"
            if exists(src):
                shutil.copy2(src, f"{out_dir}/{name}")
                break

        # Copy project.json into runtime/.VIS/ so getPath()'s walk-up
        # from the running .exe (which now lives in runtime/) finds it.
        vis_dest = f"{self.runtime}/.VIS"
        os.makedirs(vis_dest, exist_ok=True)
        src = f"{self.p_vinfo}/project.json"
        if exists(src):
            shutil.copy2(src, f"{vis_dest}/project.json")

        # Rewrite installed project.json with .pyd script paths
        installed_json = f"{vis_dest}/project.json"
        if exists(installed_json):
            with open(installed_json, "r") as f:
                info = json.load(f)
            # Prune installed project.json down to what we actually built.
            keep = {s.name for s in self.release_targets}
            for sname in list(info[self.title]["Screens"].keys()):
                if sname not in keep:
                    info[self.title]["Screens"].pop(sname)
            groups = (info[self.title].get("release_info", {})
                      .get("groups", {}))
            for gname in list(groups.keys()):
                screens = groups[gname].get("screens", [])
                # Tolerate the legacy dict-of-dicts schema during transition.
                if isinstance(screens, dict):
                    screens = list(screens.keys())
                pruned = [s for s in screens if s in keep]
                if pruned:
                    groups[gname]["screens"] = pruned
                else:
                    groups.pop(gname)
            for screen_name, screen_data in info[self.title]["Screens"].items():
                if screen_data.get("tabbed", False):
                    stem = os.path.splitext(screen_data["script"])[0]
                    screen_data["script"] = f"{stem}{_MOD_EXT}"
            with open(installed_json, "w") as f:
                json.dump(info, f, indent=4)

        # Remove any .build or .dist directories that leaked into the output
        for item in os.listdir(out_dir):
            full = os.path.join(out_dir, item)
            if os.path.isdir(full) and (item.endswith(".build") or item.endswith(".dist") or item == "_internal"):
                shutil.rmtree(full)

        # Remove Host.py if left over from a previous build
        stale_host = os.path.join(vis_dest, "Host.py")
        if os.path.exists(stale_host):
            os.remove(stale_host)

        # Layout: every Nuitka standalone build (Host + standalone screens)
        # merges into self.runtime, so all .exes share one copy of the
        # Python runtime (python3xx.dll, .pyd extensions, Tcl/Tk).
        # Uninstaller (PyInstaller --onefile, self-contained) ships at
        # the install root for user-facing accessibility.

        # "Released a new ..." banner + timing summary print at the end
        # of release() instead of here so they land after the installer
        # is actually assembled (#137).

    def newVersion(self):
        """Updates the project version, PERMANENT, cannot be undone"""
        old = str(self.Version)

        if self.type == "Major":
            self.Version.major()
        elif self.type == "Minor":
            self.Version.minor()
        elif self.type == "Patch":
            self.Version.patch()
        else:
            print(f"Unknown version type '{self.type}'. Use Major, Minor, or Patch.", flush=True)
            return False

        confirm = input(f"Version will change from {old} to {self.Version}. Proceed? (y/n): ")
        if confirm.lower() not in ("y", "yes"):
            # Revert to old version
            self.Version = Version(old)
            print("Version change cancelled.", flush=True)
            return False

        print(f"Updated Version {old} => {self.Version}", flush=True)
        return True

    def _pyinstaller_cached(self, *, src: str, pyi_name: str, cache_name: str,
                            cache_dir: str, icon_file: str, version_info_path: str,
                            extra_hidden_imports: tuple[str, ...] = (),
                            label: str = "") -> str | None:
        """Build (or reuse) a cached PyInstaller --onefile exe.

        Caches the compiled binary in ``{cache_dir}/{cache_name}[.exe]``
        and invalidates when the hash of source + icon + version_info +
        hidden imports changes.  Returns the absolute path to the cached
        exe, or ``None`` on build failure.
        """
        label = label or pyi_name
        cache_exe = f"{cache_dir}/{cache_name}" + (".exe" if sys.platform == "win32" else "")
        hash_file = f"{cache_dir}/{cache_name}.hash"

        hasher = hashlib.sha256()
        for path in (src, icon_file, version_info_path):
            with open(path, "rb") as f:
                hasher.update(f.read())
        for imp in extra_hidden_imports:
            hasher.update(imp.encode())
        current_hash = hasher.hexdigest()

        cached_hash = ""
        if os.path.exists(hash_file) and os.path.exists(cache_exe):
            with open(hash_file, "r") as f:
                cached_hash = f.read().strip()

        if cached_hash == current_hash:
            print(f"{label} source unchanged — using cached build", flush=True)
            return cache_exe

        print(f"Compiling {label} for {self.pendix}", flush=True)
        hidden_args = " ".join(
            f"--hidden-import {h}"
            for h in ("PIL._tkinter_finder", *extra_hidden_imports)
        )
        subprocess.call(
            f"pyinstaller --noconfirm --onefile "
            f"{'--uac-admin ' if sys.platform == 'win32' else ''}"
            f"--windowed --name {pyi_name} --log-level FATAL "
            f"--icon {icon_file} {hidden_args} "
            f"--version-file {version_info_path} "
            f"{src}",
            shell=True, cwd=self.location,
        )

        built = glob.glob(f"{pyi_name}*", root_dir=self.location + "dist/")
        if not built:
            print(f"Build failed: {pyi_name} not found in dist/", flush=True)
            return None
        shutil.copy2(self.location + f"dist/{built[0]}", cache_exe)
        with open(hash_file, "w") as f:
            f.write(current_hash)

        # PyInstaller artifact cleanup
        shutil.rmtree(self.location + "dist/", ignore_errors=True)
        shutil.rmtree(self.location + "build/", ignore_errors=True)
        spec = self.location + f"{pyi_name}.spec"
        if os.path.exists(spec):
            os.remove(spec)

        print(f"{label} cached for future releases", flush=True)
        return cache_exe

    @staticmethod
    def _fmt_hms(seconds: float) -> str:
        """Format ``seconds`` as ``Nh Nm Ns`` dropping leading zero
        units.  ``10s`` / ``8m 12s`` / ``1h 0m 0s``."""
        s = int(round(seconds))
        h, rem = divmod(s, 3600)
        m, s = divmod(rem, 60)
        if h:
            return f"{h}h {m}m {s}s"
        if m:
            return f"{m}m {s}s"
        return f"{s}s"

    def _print_release_summary(self, total: float,
                               phases: dict[str, float]) -> None:
        """Print the release-time summary table (#137).

        Times are right-padded with leading spaces to the longest
        formatted width so the unit suffixes (h / m / s) line up
        across rows.  ``Total`` uses a 2-space indent and its label
        is widened by the indent delta so its time column ends at
        the same character position as the 4-space-indented phase
        rows below it.
        """
        phase_label_w = max(len(name) + 1 for name in phases) if phases else 1
        all_times = [self._fmt_hms(total),
                     *(self._fmt_hms(t) for t in phases.values())]
        time_w = max(len(t) for t in all_times)
        total_label = "Total:".ljust(2 + phase_label_w)
        print(f"  {total_label}  {self._fmt_hms(total):>{time_w}}",
              flush=True)
        for name, t in phases.items():
            label = (name + ":").ljust(phase_label_w)
            print(f"    {label}  {self._fmt_hms(t):>{time_w}}",
                  flush=True)

    def release(self):
        """Releases a version of your project"""
        # Validation in __init__ already printed an error if any.
        if self.release_targets is None:
            return

        release_start = time.monotonic()
        phase_times: dict[str, float] = {}

        #Pre-flight: compiler + patchelf (Linux) + required Python tools.
        #Fail fast with actionable messages before any version bumps,
        #user prompts, or compilation work.
        if not self._check_compiler():
            return
        if not self._check_patchelf():
            return
        if not self._check_tools():
            return

        #Ensure dist + build roots exist.  ``build_dir`` is intentionally
        #not wiped here — its .build/ subfolders are Nuitka's per-module
        #cache and persist between runs (#91).
        os.makedirs(self.location, exist_ok=True)
        os.makedirs(self.build_dir, exist_ok=True)

        #Wipe runtime/ from any previous build.  Without this, leftover
        #per-screen .exes (from the old pre-always-Host pipeline) or
        #stale source .py files from older flows persist into the new
        #install, both bloating binaries.zip and tripping the runtime's
        #dev/release detection in TabManager._load_screen_codes.
        if os.path.isdir(self.runtime):
            shutil.rmtree(self.runtime)

        #Check default screen
        if self.default_screen is None:
            print("Warning: No default screen set in project.json.", flush=True)
            print("The Host will launch with no visible window.", flush=True)
            confirm = input("Continue anyway? (y/n): ")
            if confirm.lower() not in ("y", "yes"):
                return

        #Check Version
        if self.type != "":
            if not self.newVersion():
                return

        #Compile — count steps per category
        shared_pkgs = [imp for imp in self.hidden_imports if "." not in imp]
        for pkg in self.collect_packages:
            if pkg not in shared_pkgs:
                shared_pkgs.append(pkg)
        pkg_count = len(shared_pkgs)

        # Every release target produces one wrapper .pyd — tabbed and
        # standalone alike — so the Host can open it as a tab.  Under
        # the always-Host model there are no per-screen .exes; the Host
        # binary is the only one in the install.
        screen_count = len(self.release_targets)
        binary_count = 1  # Host .exe only

        all_screens = self.Groups[Group.ALL].screenlist
        if len(self.release_targets) < len([s for s in all_screens if s.tabbed or s.release]):
            print(f"Partial release: {len(self.release_targets)} screen(s) included.",
                  flush=True)

        total = pkg_count + screen_count + binary_count
        self._step = 0
        self._total_steps = total
        print(f"\n{self.title} Release - {total} Compilations", flush=True)

        # Required Packages (.pyd)
        self._category = "Required Packages"
        self._cat_index = 0
        self._cat_count = pkg_count
        t0 = time.monotonic()
        if not self.compile_shared():
            self._status("", newline=True)
            print(f"\nRelease FAILED during Required Packages.", flush=True)
            return
        phase_times["Required Packages"] = time.monotonic() - t0

        # Screen wrappers (.pyd) — one per release target, parallel
        self._category = "Screens"
        self._cat_index = 0
        self._cat_count = screen_count
        t0 = time.monotonic()
        if not self.compile_screens(mode="pyd"):
            self._status("", newline=True)
            print(f"\nRelease FAILED during Screen wrapper compilation.", flush=True)
            return
        phase_times["Screens"] = time.monotonic() - t0

        # Host binary (.exe) — the only binary under the always-Host model
        self._category = "Host"
        self._cat_index = 0
        self._cat_count = binary_count
        t0 = time.monotonic()
        if not self.compile_screens(mode="exe"):
            self._status("", newline=True)
            print(f"\nRelease FAILED during Host compilation.", flush=True)
            return

        self._status("", newline=True)
        phase_times["Host"] = time.monotonic() - t0

        installer_t0 = time.monotonic()
        #Clean Environment — copies Images/, Icons/, and .VIS/project.json
        #into self.final so they end up in binaries.zip.  Without this the
        #installer's appended-archive load raises KeyError on .VIS/project.json
        #and the --windowed exe dies before any window appears.
        self.clean()

        # Post-condition: the Host .exe must be present in runtime/.  No
        # per-screen .exes to check anymore — every screen opens through
        # the Host as a tab or chromeless DetachedWindow.
        expected_host = os.path.join(self.runtime, f"{self.title}{_EXE_EXT}")
        if not exists(expected_host):
            print(
                f"\nRelease FAILED: Host binary missing from {self.runtime}: "
                f"{self.title}{_EXE_EXT}.  Inspect the build output above "
                f"for the underlying failure.",
                flush=True,
            )
            return

        #%Installer & Uninstaller Generation
        binaries_zip = f"{self.location}binaries.zip"

        #Resolve icon for installer and uninstaller
        with open(self.p_sinfo, "r") as f:
            _inst_info = json.load(f)
        installer_icon_name = _inst_info[self.title].get("metadata", {}).get("installer_icon", self.d_icon)
        ixt = ".ico" if sys.platform == "win32" else ".xbm"
        icon_file = self.p_project + "/Icons/" + installer_icon_name + ixt
        if not exists(icon_file):
            # Fall back to default app icon
            icon_file = self.p_project + "/Icons/" + self.d_icon + ixt

        cache_dir = self.p_vinfo + "/cache"
        os.makedirs(cache_dir, exist_ok=True)

        # Generate version info file for PyInstaller builds
        ver_parts = str(self.Version).split(".")
        ver_tuple = ", ".join(ver_parts + ["0"] * (4 - len(ver_parts)))
        ver_str = str(self.Version)
        year = datetime.datetime.now().year
        version_info_path = cache_dir + "/version_info.txt"
        _esc = lambda s: s.replace("'", "\\'") if s else ""
        with open(version_info_path, "w") as vf:
            vf.write(f"""VSVersionInfo(
  ffi=FixedFileInfo(filevers=({ver_tuple}), prodvers=({ver_tuple})),
  kids=[
    StringFileInfo([
      StringTable('040904B0', [
        StringStruct('CompanyName', '{_esc(self.company)}'),
        StringStruct('FileDescription', '{_esc(self.title)} Installer'),
        StringStruct('FileVersion', '{ver_str}'),
        StringStruct('LegalCopyright', 'Copyright {year} {_esc(self.company)}'),
        StringStruct('OriginalFilename', '{_esc(self.pendix)}_Installer.exe'),
        StringStruct('ProductName', '{_esc(self.title)}'),
        StringStruct('ProductVersion', '{ver_str}'),
      ])
    ]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
""")

        #%Uninstaller compilation (cached)
        cache_uninstaller = self._pyinstaller_cached(
            src=VISROOT.replace("\\","/") + "Structures/Uninstaller.py",
            pyi_name="Uninstaller",
            cache_name="uninstaller_base",
            cache_dir=cache_dir,
            icon_file=icon_file,
            version_info_path=version_info_path,
            label="Uninstaller",
        )
        if cache_uninstaller is None:
            return

        #Copy uninstaller into build output so it ends up in binaries.zip
        uninst_dest_name = "Uninstaller.exe" if sys.platform == "win32" else "Uninstaller"
        shutil.copy2(cache_uninstaller, f"{self.final}/{uninst_dest_name}")
        print(f"Uninstaller included in release: {uninst_dest_name}", flush=True)

        #Create binaries.zip from built output
        print(f"Creating binaries.zip from {self.final} for installer", flush=True)
        shutil.make_archive(base_name=f"{self.location}binaries", format="zip", root_dir=self.final)

        #%Installer compilation (cached)
        cache_base = self._pyinstaller_cached(
            src=VISROOT.replace("\\","/") + "Structures/Installer.py",
            pyi_name="installer_base",
            cache_name="installer_base",
            cache_dir=cache_dir,
            icon_file=icon_file,
            version_info_path=version_info_path,
            extra_hidden_imports=("psutil",),
            label="Base installer",
        )
        if cache_base is None:
            return

        #Concatenate: cached base exe + binaries.zip = final installer
        installer_name = f"{self.pendix}_Installer"
        if sys.platform == "win32":
            installer_name += ".exe"
        final_installer = f"{self.p_project}/{installer_name}"

        print(f"Assembling {installer_name} (base + binaries.zip)", flush=True)
        if os.path.exists(final_installer):
            os.remove(final_installer)
        with open(final_installer, "wb") as out:
            with open(cache_base, "rb") as base:
                out.write(base.read())
            with open(binaries_zip, "rb") as data:
                out.write(data.read())

        # Preserve binaries.zip for debugging archive issues; next release
        # overwrites it via shutil.make_archive(), so it doesn't accumulate.

        #Move installer to Downloads folder
        from pathlib import Path as _Path
        downloads_installer = str(_Path.home() / "Downloads" / installer_name)
        if os.path.exists(downloads_installer):
            os.remove(downloads_installer)
        shutil.move(final_installer, downloads_installer)
        print(f"Installer ready: {downloads_installer}", flush=True)
        phase_times["Installer"] = time.monotonic() - installer_t0

        # Release-complete banner moved out of clean() so it lands
        # after the installer is actually ready (#137).
        print(
            f"\n\nReleased a new"
            f"{' '+self.flag+' ' if self.flag else ' '}"
            f"build of {self.title}!",
            flush=True,
        )
        self._print_release_summary(
            time.monotonic() - release_start, phase_times,
        )
