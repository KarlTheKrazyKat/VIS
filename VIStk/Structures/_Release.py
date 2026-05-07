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
import json
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

        # Top-level packages that compile_shared ships as standalone
        # ``<pkg>.pyd`` files at the install root.  Every other phase
        # adds ``--no-follow-import-to={pkg}`` for each of these so its
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
                # C file compilation progress
                m = _re.search(r'Compiled (\d+)[/ ](?:out of )?(\d+)', segment)
                if m:
                    self._status(f"{prefix} — C {m.group(1)}/{m.group(2)}")
                    continue
                if 'Backend C linking' in segment:
                    self._status(f"{prefix} — linking")
                    continue
                # Capture last FATAL/error line for failure reporting
                if 'FATAL' in segment or 'error:' in segment.lower():
                    last_error = segment

        proc.wait()
        if proc.returncode != 0:
            # Print failure on its own line so it stays visible
            msg = f"{prefix} FAILED"
            if last_error:
                msg += f" — {last_error[:60]}"
            self._status(msg, newline=True)
            return False
        return True

    def compile_host(self):
        """Compile the Host as a standalone Nuitka executable.

        Nuitka names the output folder after the entry script stem
        (e.g. ``Host.dist``).  After compilation the contents are merged
        into the final distribution folder (e.g. ``dist/PYWOM/``).
        """
        ixt = ".ico" if sys.platform == "win32" else ".xbm"
        icon_file = f"{self.p_project}/Icons/{self.d_icon}{ixt}"

        # Read nuitka config from project.json
        with open(self.p_sinfo, "r") as f:
            info = json.load(f)
        nuitka_cfg = info[self.title].get("release_info", {}).get("nuitka", {})
        onefile = nuitka_cfg.get("onefile", False)
        extra_args = nuitka_cfg.get("extra_args", [])

        mode = "--onefile" if onefile else "--standalone"

        parts = [sys.executable, "-m", "nuitka", mode]
        parts.extend(self._compiler_args())
        parts.append("--follow-imports")
        parts.append("--enable-plugin=tk-inter")

        # Hidden imports.  Top-level packages already ship as their own
        # ``<pkg>.pyd`` at install root (compile_shared) — bundling them
        # again here would create duplicate copies that diverge from the
        # external one.  So we add ``--no-follow-import-to`` instead.
        # Dotted names (e.g. ``PIL._tkinter_finder``) are module-level
        # hints and stay as ``--include-module``.
        for imp in self.hidden_imports:
            if "." not in imp:
                parts.append(f"--no-follow-import-to={imp}")
            else:
                parts.append(f"--include-module={imp}")

        # Tabbed screens ship as standalone ``Screens/<name>.pyd`` files
        # and per-screen logic ships as ``modules/<name>.pyd`` — both are
        # external so replacing one .pyd updates that screen without
        # rebuilding the Host.  Don't bundle either.
        parts.append("--no-follow-import-to=Screens")
        parts.append("--no-follow-import-to=modules")

        # Icon
        if icon_file and exists(icon_file):
            parts.append(f"--windows-icon-from-ico={icon_file}")

        # Company and product info
        if self.company:
            parts.append(f"--windows-company-name={self.company}")
            parts.append(f"--windows-product-name={self.title}")
            year = datetime.datetime.now().year
            parts.append(f"--windows-file-description={self.title}")
            parts.append(f"--copyright=Copyright {year} {self.company}")

        parts.append(f"--windows-product-version={self.Version}")

        parts.append(f"--output-dir={self.build_dir}")
        parts.append(f"--output-filename={self.title}{_EXE_EXT}")

        if sys.platform == "win32":
            parts.append("--windows-console-mode=disable")

        parts.append("--assume-yes-for-downloads")

        # Extra args from project.json
        parts.extend(extra_args)

        # Entry script is the Host
        entry_script = self.host_script
        parts.append(entry_script)

        ok = self._run_nuitka(parts, self.title, self.p_project)

        if not ok:
            return False

        # Nuitka names the .dist folder after the entry script stem
        host_stem = os.path.splitext(os.path.basename(entry_script))[0]
        nuitka_dist = f"{self.build_dir}{host_stem}.dist"

        _skip = {'.build', '_internal', '__pycache__'}
        if exists(nuitka_dist):
            if exists(self.final):
                # Merge new build into existing folder (preserves screen exes etc.)
                for dirpath, dirs, files in os.walk(nuitka_dist):
                    dirs[:] = [d for d in dirs if d not in _skip and not d.endswith('.build')]
                    rel = os.path.relpath(dirpath, nuitka_dist)
                    dest = os.path.join(self.final, rel)
                    os.makedirs(dest, exist_ok=True)
                    for f in files:
                        src = os.path.join(dirpath, f)
                        shutil.copy2(src, os.path.join(dest, f))
                shutil.rmtree(nuitka_dist)
            else:
                os.rename(nuitka_dist, self.final)

        return True

    def compile_screens(self, mode="all"):
        """Compile each screen plus its per-screen modules sub-package.

        For every tabbed screen in ``release_targets``, two artifacts
        ship to the install:

        * ``Screens/<name>.pyd`` — the screen's UI entry, compiled from
          ``<name>.py``.
        * ``modules/<name>.pyd`` — the screen's logic sub-package,
          compiled from ``modules/<name>/`` (only when that directory
          exists).

        Both kinds of jobs share one parallel call so workers stay busy.
        Workers default to ``cpu_count // 2`` to leave headroom for
        Nuitka's per-process C compiler subprocesses.

        Standalone screens (``tabbed=false``) with ``release=true`` stay
        serial — each is ``--standalone`` and merges its ``.dist`` into
        the shared ``self.final`` directory, where concurrent merges
        would race on common runtime files (python3xx.dll, etc.).

        ``mode`` filters which screens to compile: ``"pyd"`` for tabbed
        screens (and their modules), ``"exe"`` for standalone release
        screens only, or ``"all"`` for both (default).
        """
        ixt = ".ico" if sys.platform == "win32" else ".xbm"

        if mode in ("all", "pyd"):
            tabbed = [s for s in self.release_targets if s.tabbed]
            modules = self._modules_for_release()
            if tabbed or modules:
                if tabbed:
                    os.makedirs(f"{self.final}/Screens", exist_ok=True)
                if modules:
                    os.makedirs(f"{self.final}/modules", exist_ok=True)
                if not self._compile_pyds_parallel(tabbed, modules):
                    return False

        if mode in ("all", "exe"):
            for scr in self.release_targets:
                if scr.tabbed:
                    continue
                if not self._compile_screen_exe(scr, ixt):
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

    def _compile_screen_pyd(self, scr) -> tuple[bool, str]:
        """Compile one tabbed screen → ``final/Screens/<stem>.pyd``.

        Threadsafe — uses :meth:`_run_nuitka_silent` so concurrent calls
        don't fight over the progress display.  Returns ``(ok, error)``.
        """
        stem = os.path.splitext(scr.script)[0]
        parts = [
            sys.executable, "-m", "nuitka", "--module",
            *self._compiler_args(),
            # Cross-screen imports stay runtime-resolved.  Shared packages
            # and other-screen modules ship as their own .pyds at install
            # root / modules/ and are excluded so they aren't bundled
            # (would create duplicate-module hazards like mismatched
            # isinstance across copies).
            "--no-follow-import-to=Screens",
            "--no-follow-import-to=modules",
            f"--output-dir={self.build_dir}",
            "--assume-yes-for-downloads",
        ]
        for pkg in self.shared_pkg_names:
            parts.append(f"--no-follow-import-to={pkg}")
        parts.append(scr.script)

        ok, err = self._run_nuitka_silent(parts, self.p_project)
        if not ok:
            return False, err or "nuitka returned non-zero"

        built_mods = glob.glob(f"{self.build_dir}{stem}*{_MOD_EXT}")
        if not built_mods:
            return False, f"no {_MOD_EXT} produced at {self.build_dir}{stem}*{_MOD_EXT}"
        for bp in built_mods:
            shutil.move(bp, f"{self.final}/Screens/{stem}{_MOD_EXT}")
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

    def _compile_pyds_parallel(self, screens: list, modules: list) -> bool:
        """Compile screens and their modules sub-packages concurrently.

        Both job kinds run in the same ``ThreadPoolExecutor`` so workers
        stay busy.  Workers default to ``cpu_count // 2`` to leave
        headroom for Nuitka's per-process C compiler subprocesses.
        """
        max_workers = max(1, (os.cpu_count() or 4) // 2)
        jobs = []
        for s in screens:
            jobs.append((s.name, lambda s=s: self._compile_screen_pyd(s)))
        for name, path in modules:
            jobs.append((f"modules.{name}",
                         lambda n=name, p=path: self._compile_one_module(n, p)))
        return self._run_parallel(jobs, "module", max_workers)

    def _compile_one_module(self, screen_name: str, mod_path: str) -> tuple[bool, str]:
        """Compile ``modules/<screen>/`` → ``final/modules/<screen>.pyd``.

        Each job uses an isolated build subdir to avoid colliding with
        the matching screen's ``.pyd`` compile (both produce a ``.pyd``
        whose stem is the screen's leaf name, so they'd otherwise stomp
        each other's intermediates inside ``self.build_dir``).

        Threadsafe — uses :meth:`_run_nuitka_silent`.
        """
        out_dir = f"{self.build_dir}modules_{screen_name}/"
        os.makedirs(out_dir, exist_ok=True)
        parts = [
            sys.executable, "-m", "nuitka", "--module",
            *self._compiler_args(),
            f"--include-package=modules.{screen_name}",
            f"--output-dir={out_dir}",
            "--assume-yes-for-downloads",
            "--no-follow-import-to=Screens",
        ]
        for pkg in self.shared_pkg_names:
            parts.append(f"--no-follow-import-to={pkg}")
        parts.append(mod_path)

        ok, err = self._run_nuitka_silent(parts, self.p_project)
        if not ok:
            return False, err or "nuitka returned non-zero"

        built = glob.glob(f"{out_dir}*{_MOD_EXT}")
        if not built:
            return False, f"no {_MOD_EXT} produced for modules.{screen_name}"
        target = f"{self.final}/modules/{screen_name}{_MOD_EXT}"
        # If multiple .pyds came out, pick the one that matches the leaf
        # (Nuitka may emit a cpython-tagged sibling).  Prefer exact stem.
        primary = next((bp for bp in built
                        if os.path.basename(bp).startswith(f"{screen_name}.")
                        or os.path.basename(bp).startswith(f"{screen_name}{_MOD_EXT}")),
                       built[0])
        shutil.move(primary, target)
        return True, ""

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
        excluded with ``--no-follow-import-to`` so this build doesn't end
        up containing a copy of, say, VIStk inside pywomlib.pyd.

        Threadsafe — uses :meth:`_run_nuitka_silent`.
        """
        parts = [
            sys.executable, "-m", "nuitka", "--module",
            *self._compiler_args(),
            # See compile_shared() for why --include-package is required.
            f"--include-package={pkg}",
            f"--output-dir={self.build_dir}",
            "--assume-yes-for-downloads",
        ]
        for peer in self.shared_pkg_names:
            if peer != pkg:
                parts.append(f"--no-follow-import-to={peer}")
        parts.append(pkg_path)

        ok, err = self._run_nuitka_silent(parts, self.p_project)
        if not ok:
            return False, err or "nuitka returned non-zero"

        built = glob.glob(f"{self.build_dir}{pkg}*{_MOD_EXT}")
        if not built:
            return False, f"no {_MOD_EXT} produced at {self.build_dir}{pkg}*{_MOD_EXT}"
        for bp in built:
            shutil.move(bp, f"{self.final}/{pkg}{_MOD_EXT}")
        return True, ""

    def _compile_screen_exe(self, scr, ixt: str) -> bool:
        """Compile one standalone screen → ``final/<scr.name>.exe``.

        Kept serial because each ``--standalone`` build merges its
        ``.dist/`` into ``self.final`` and concurrent merges would race
        on common runtime files.
        """
        icon = (scr.icon if scr.icon else self.d_icon) + ixt
        icon_file = f"{self.p_project}/Icons/{icon}"

        parts = [
            sys.executable, "-m", "nuitka", "--standalone",
            *self._compiler_args(),
            "--enable-plugin=tk-inter",
            f"--output-dir={self.build_dir}",
            f"--output-filename={scr.name}{_EXE_EXT}",
            "--assume-yes-for-downloads",
        ]
        if icon_file and exists(icon_file):
            parts.append(f"--windows-icon-from-ico={icon_file}")
        if self.company:
            parts.append(f"--windows-company-name={self.company}")
            parts.append(f"--windows-product-name={self.title}")
            year = datetime.datetime.now().year
            parts.append(f"--windows-file-description={scr.name}")
            parts.append(f"--copyright=Copyright {year} {self.company}")
        parts.append(f"--windows-product-version={self.Version}")
        if sys.platform == "win32":
            parts.append("--windows-console-mode=disable")
        # Standalone screens share the Host runtime at the install root
        # (python3xx.dll, .pyd, third-party packages).  Follow direct
        # imports only — shared packages, other screens, and per-screen
        # modules live alongside as their own .pyds and must not be
        # bundled in.
        parts.append("--follow-imports")
        parts.append("--no-follow-import-to=Screens")
        parts.append("--no-follow-import-to=modules")
        for pkg in self.shared_pkg_names:
            parts.append(f"--no-follow-import-to={pkg}")
        parts.append(scr.script)

        ok = self._run_nuitka(parts, scr.name, self.p_project)
        if not ok:
            return False

        scr_stem = os.path.splitext(scr.script)[0]
        scr_dist = f"{self.build_dir}{scr_stem}.dist"
        if not exists(scr_dist):
            # Nuitka exited 0 but produced no .dist — fail loudly rather
            # than silently shipping an installer without this screen's
            # exe (issue #115).
            try:
                siblings = sorted(os.listdir(self.build_dir))
            except OSError:
                siblings = []
            self._status(
                f"  [{self._step}/{self._total_steps}] {self._category} "
                f"{self._cat_index}/{self._cat_count} - {scr.name} FAILED — "
                f"expected {scr_dist} not produced (build_dir contains: "
                f"{', '.join(siblings) or 'nothing'})",
                newline=True,
            )
            return False
        _skip = {'.build', '_internal', '__pycache__'}
        for dirpath, dirs, files in os.walk(scr_dist):
            dirs[:] = [d for d in dirs if d not in _skip and not d.endswith('.build')]
            rel = os.path.relpath(dirpath, scr_dist)
            dest = os.path.join(self.final, rel)
            os.makedirs(dest, exist_ok=True)
            for f in files:
                dest_file = os.path.join(dest, f)
                if not exists(dest_file):
                    shutil.copy2(os.path.join(dirpath, f), dest_file)
        shutil.rmtree(scr_dist)

        expected_exe = os.path.join(self.final, f"{scr.name}{_EXE_EXT}")
        if not exists(expected_exe):
            self._status(
                f"  [{self._step}/{self._total_steps}] {self._category} "
                f"{self._cat_index}/{self._cat_count} - {scr.name} FAILED — "
                f"expected {expected_exe} after merge but it is missing",
                newline=True,
            )
            return False
        return True

    def compile_shared(self):
        """Compile shared packages as .pyd modules into Shared/.

        Top-level packages from ``hidden_imports`` (names without dots) are
        compiled here.  Module-level hints like ``PIL._tkinter_finder`` are
        skipped — those are passed to the Host build instead.

        ``collect_packages`` entries are also compiled if present.
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

        os.makedirs(self.final, exist_ok=True)
        return self._compile_shared_parallel(resolved)

    def clean(self):
        """Appends project data to dist folder.

        Copies Images, .VIS/project.json, and writes an installed
        project.json with rewritten screen script paths.  Removes any
        stray Nuitka ``.build`` directories from the output.
        """
        print("Appending Screen Data To Environment", flush=True)

        out_dir = self.final

        # Copy Images
        src = f"{self.p_project}/Images/"
        if exists(src):
            shutil.copytree(src, f"{out_dir}/Images/", dirs_exist_ok=True)

        # Copy Icons
        src = f"{self.p_project}/Icons/"
        if exists(src):
            shutil.copytree(src, f"{out_dir}/Icons/", dirs_exist_ok=True)

        # Copy license file if present
        for name in ("LICENSE", "LICENSE.txt", "EULA.txt", "EULA.md"):
            src = f"{self.p_project}/{name}"
            if exists(src):
                shutil.copy2(src, f"{out_dir}/{name}")
                break

        # Copy project.json only (Host.py is compiled into the exe)
        vis_dest = f"{out_dir}/.VIS"
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
                    screen_data["script"] = f"Screens/{stem}{_MOD_EXT}"
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

        # The Nuitka standalone exes live at the install root alongside
        # their python313.dll / .pyd / package dependencies.  No .Runtime/
        # indirection layer, no launcher shim — see #105.

        print(f"\n\nReleased a new{' '+self.flag+' ' if self.flag else ' '}build of {self.title}!", flush=True)

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

    def release(self):
        """Releases a version of your project"""
        # Validation in __init__ already printed an error if any.
        if self.release_targets is None:
            return

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

        screen_count = sum(1 for s in self.release_targets if s.tabbed)
        module_count = len(self._modules_for_release())
        binary_count = sum(1 for s in self.release_targets if not s.tabbed) + 1  # +1 = Host

        all_screens = self.Groups[Group.ALL].screenlist
        if len(self.release_targets) < len([s for s in all_screens if s.tabbed or s.release]):
            print(f"Partial release: {len(self.release_targets)} screen(s) included.",
                  flush=True)

        total = pkg_count + screen_count + module_count + binary_count
        self._step = 0
        self._total_steps = total
        print(f"\n{self.title} Release - {total} Compilations", flush=True)

        # Required Packages (.pyd)
        self._category = "Required Packages"
        self._cat_index = 0
        self._cat_count = pkg_count
        if not self.compile_shared():
            self._status("", newline=True)
            print(f"\nRelease FAILED during Required Packages.", flush=True)
            return

        # Screens + Modules (.pyd) — same parallel call
        self._category = "Modules"
        self._cat_index = 0
        self._cat_count = screen_count + module_count
        if not self.compile_screens(mode="pyd"):
            self._status("", newline=True)
            print(f"\nRelease FAILED during Screen/Module compilation.", flush=True)
            return

        # Binaries (.exe)
        self._category = "Binaries"
        self._cat_index = 0
        self._cat_count = binary_count
        if not self.compile_screens(mode="exe"):
            self._status("", newline=True)
            print(f"\nRelease FAILED during Binary compilation.", flush=True)
            return
        if not self.compile_host():
            self._status("", newline=True)
            print(f"\nRelease FAILED during Host compilation.", flush=True)
            return

        self._status("", newline=True)

        #Clean Environment
        #self.clean()

        # Nuitka exes live at the install root and are launched directly.
        # No PyInstaller launcher shim, no .Runtime/ indirection — see #105.

        # Post-condition: every standalone screen we said we'd build must
        # have its exe present at the install root.  Catches silent
        # failures further upstream (issue #115) so we don't ship a
        # binaries.zip that's missing the screens the user paid to compile.
        missing_exes = []
        for scr in self.release_targets:
            if scr.tabbed:
                continue
            expected = os.path.join(self.final, f"{scr.name}{_EXE_EXT}")
            if not exists(expected):
                missing_exes.append(scr.name)
        if missing_exes:
            print(
                f"\nRelease FAILED: standalone exe(s) missing from {self.final}: "
                f"{', '.join(missing_exes)}.  Inspect the build output above "
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

        #Clean up temporary binaries.zip
        os.remove(binaries_zip)

        #Move installer to Downloads folder
        from pathlib import Path as _Path
        downloads_installer = str(_Path.home() / "Downloads" / installer_name)
        if os.path.exists(downloads_installer):
            os.remove(downloads_installer)
        shutil.move(final_installer, downloads_installer)
        print(f"Installer ready: {downloads_installer}", flush=True)
