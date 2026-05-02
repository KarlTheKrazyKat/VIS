from VIStk.Structures._Project import *
from VIStk.Structures._VINFO import *
from VIStk.Structures._Screen import *
import re as _re
import subprocess
import shutil
import glob
from os.path import exists
from zipfile import *
import datetime
import hashlib
import json
from VIStk.Structures._Version import Version


class Release(Project):
    """A VIS Release object"""
    def __init__(self, flag:str="",type:str="",note:str="",
                 subset_groups: list[str] | None = None,
                 subset_screens: list[str] | None = None):
        """Creates a Release object to release or examine a release of a project

        ``subset_groups`` and ``subset_screens`` scope the build to a subset of
        screens. When both are ``None`` every screen is built (existing
        behaviour). When either is provided, only screens in that union are
        compiled; the Host is always included. The resulting installer's
        embedded ``project.json`` is pruned to the same subset.
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

        self._subset_screens: set[str] | None = self._resolve_subset(
            subset_groups, subset_screens
        )
        """Set of screen names included in this build, or None for all."""

    def _resolve_subset(self, subset_groups, subset_screens) -> set[str] | None:
        if not subset_groups and not subset_screens:
            return None
        names: set[str] = set()
        if subset_groups:
            groups = self.groups()
            for g in subset_groups:
                if g not in groups:
                    print(f"Warning: group '{g}' not found; skipping.", flush=True)
                    continue
                for s in groups[g].get("screens", {}).keys():
                    names.add(s)
        if subset_screens:
            for s in subset_screens:
                if not self.hasScreen(s):
                    print(f"Warning: screen '{s}' not found; skipping.", flush=True)
                    continue
                names.add(s)
        if not names:
            print("Warning: subset resolved to zero screens; aborting.", flush=True)
        return names

    def _screen_in_subset(self, scr) -> bool:
        """True if ``scr`` should be compiled in this build."""
        return self._subset_screens is None or scr.name in self._subset_screens

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

    def _status(self, text: str, newline: bool = False):
        """Overwrite the single progress line. Pads to _LINE_WIDTH."""
        end = "\n" if newline else ""
        sys.stdout.write(f"\r{text:<{self._LINE_WIDTH}}{end}")
        sys.stdout.flush()

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
        pendix = self.title if self.flag == "" else f"{self.title}-{self.flag}"
        final = f"{self.location}{pendix}"

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

        # Include hidden imports.
        # Top-level packages (no dots) use --include-package so all sub-packages
        # are bundled into the exe.  Dotted names (e.g. PIL._tkinter_finder) are
        # module-level hints and use --include-module.
        for imp in self.hidden_imports:
            if "." not in imp:
                parts.append(f"--include-package={imp}")
            else:
                parts.append(f"--include-module={imp}")

        # Bundle project packages so screen .pyds can resolve imports at runtime
        parts.append("--include-package=modules")
        parts.append("--include-package=Screens")

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
        parts.append(f"--output-filename={self.title}.exe")

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
            if exists(final):
                # Merge new build into existing folder (preserves screen exes etc.)
                for dirpath, dirs, files in os.walk(nuitka_dist):
                    dirs[:] = [d for d in dirs if d not in _skip and not d.endswith('.build')]
                    rel = os.path.relpath(dirpath, nuitka_dist)
                    dest = os.path.join(final, rel)
                    os.makedirs(dest, exist_ok=True)
                    for f in files:
                        src = os.path.join(dirpath, f)
                        shutil.copy2(src, os.path.join(dest, f))
                shutil.rmtree(nuitka_dist)
            else:
                os.rename(nuitka_dist, final)

        return True

    def compile_screens(self, mode="all"):
        """Compile each screen.

        Every tabbed screen is compiled as a ``.pyd`` module in ``Screens/``
        so the Host can load it dynamically at runtime.  The default screen
        is skipped (it's the Host entry point compiled separately).

        Standalone screens (``tabbed=false``) with ``release=true`` are
        compiled as their own ``.exe`` and merged into the Host dist folder
        so they share the runtime.

        ``mode`` filters which screens to compile: ``"pyd"`` for tabbed
        screens only, ``"exe"`` for standalone release screens only, or
        ``"all"`` for both (default).
        """
        pendix = self.title if self.flag == "" else f"{self.title}-{self.flag}"
        final = f"{self.location}{pendix}"
        ixt = ".ico" if sys.platform == "win32" else ".xbm"

        has_tabbed = False
        for scr in self.screenlist:
            if not self._screen_in_subset(scr):
                continue

            if scr.tabbed and mode in ("all", "pyd"):
                # Every tabbed screen → .pyd module
                if not has_tabbed:
                    os.makedirs(f"{final}/Screens", exist_ok=True)
                    has_tabbed = True

                stem = os.path.splitext(scr.script)[0]
                parts = [
                    sys.executable, "-m", "nuitka", "--module",
                    *self._compiler_args(),
                    f"--output-dir={self.build_dir}",
                    "--assume-yes-for-downloads",
                    scr.script,
                ]
                ok = self._run_nuitka(parts, scr.name, self.p_project)

                if not ok:
                    return False

                # Move .pyd to Screens/ with clean name (strip cpython tag)
                import glob as _glob
                built_pyds = _glob.glob(f"{self.build_dir}{stem}*.pyd")
                for bp in built_pyds:
                    shutil.move(bp, f"{final}/Screens/{stem}.pyd")

            elif not scr.tabbed and scr.release and mode in ("all", "exe"):
                # Standalone screen with release=true — compile as its own exe
                icon = (scr.icon if scr.icon else self.d_icon) + ixt
                icon_file = f"{self.p_project}/Icons/{icon}"

                parts = [
                    sys.executable, "-m", "nuitka", "--standalone",
                    *self._compiler_args(),
                    "--enable-plugin=tk-inter",
                    f"--output-dir={self.build_dir}",
                    f"--output-filename={scr.name}.exe",
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
                # Standalone screens share the Host runtime at the install
                # root (python313.dll, .pyd, third-party packages).  Follow
                # direct imports only — shared packages live alongside.
                parts.append("--follow-imports")
                parts.append(scr.script)

                ok = self._run_nuitka(parts, scr.name, self.p_project)

                if not ok:
                    return False

                # Merge standalone build into the shared dist folder
                scr_stem = os.path.splitext(scr.script)[0]
                scr_dist = f"{self.build_dir}{scr_stem}.dist"
                if exists(scr_dist):
                    _skip = {'.build', '_internal', '__pycache__'}
                    for dirpath, dirs, files in os.walk(scr_dist):
                        dirs[:] = [d for d in dirs if d not in _skip and not d.endswith('.build')]
                        rel = os.path.relpath(dirpath, scr_dist)
                        dest = os.path.join(final, rel)
                        os.makedirs(dest, exist_ok=True)
                        for f in files:
                            dest_file = os.path.join(dest, f)
                            if not exists(dest_file):
                                shutil.copy2(os.path.join(dirpath, f), dest_file)
                    shutil.rmtree(scr_dist)

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

        pendix = self.title if self.flag == "" else f"{self.title}-{self.flag}"
        final = f"{self.location}{pendix}"
        shared_dir = f"{final}/Shared"
        os.makedirs(shared_dir, exist_ok=True)

        for pkg in packages:
            # Resolve the installed package path
            try:
                mod = __import__(pkg)
                pkg_path = os.path.dirname(mod.__file__)
            except Exception:
                print(f"  Skipping {pkg} — not importable", flush=True)
                continue

            parts = [
                sys.executable, "-m", "nuitka", "--module",
                *self._compiler_args(),
                f"--output-dir={self.build_dir}",
                "--assume-yes-for-downloads",
                pkg_path,
            ]
            ok = self._run_nuitka(parts, pkg, self.p_project)

            if not ok:
                return False

            # Move .pyd to Shared/ directory — strip cpython tag
            import glob as _glob
            built_pyds = _glob.glob(f"{self.build_dir}{pkg}*.pyd")
            for bp in built_pyds:
                shutil.move(bp, f"{shared_dir}/{pkg}.pyd")

        return True

    def clean(self):
        """Appends project data to dist folder.

        Copies Images, .VIS/project.json, and writes an installed
        project.json with rewritten screen script paths.  Removes any
        stray Nuitka ``.build`` directories from the output.
        """
        print("Appending Screen Data To Environment", flush=True)

        pendix = self.title if self.flag == "" else f"{self.title}-{self.flag}"
        out_dir = f"{self.location}{pendix}"

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
            # Prune screens not in the subset (0.4.6)
            if self._subset_screens is not None:
                keep = self._subset_screens
                for sname in list(info[self.title]["Screens"].keys()):
                    if sname not in keep:
                        info[self.title]["Screens"].pop(sname)
                groups = (info[self.title].get("release_info", {})
                          .get("groups", {}))
                for gname in list(groups.keys()):
                    screens = groups[gname].get("screens", {})
                    for sn in list(screens.keys()):
                        if sn not in keep:
                            screens.pop(sn)
                    if not screens:
                        groups.pop(gname)
            for screen_name, screen_data in info[self.title]["Screens"].items():
                if screen_data.get("tabbed", False):
                    stem = os.path.splitext(screen_data["script"])[0]
                    screen_data["script"] = f"Screens/{stem}.pyd"
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

    def release(self):
        """Releases a version of your project"""
        #Pre-flight: compiler + required Python tools.
        #Fail fast with actionable messages before any version bumps,
        #user prompts, or compilation work.
        if not self._check_compiler():
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

        #Clean previous build output
        pendix = self.title if self.flag == "" else f"{self.title}-{self.flag}"
        final = f"{self.location}{pendix}"
        if exists(final):
            shutil.rmtree(final)

        #Compile — count steps per category
        shared_pkgs = [imp for imp in self.hidden_imports if "." not in imp]
        for pkg in self.collect_packages:
            if pkg not in shared_pkgs:
                shared_pkgs.append(pkg)
        pkg_count = len(shared_pkgs)

        screen_count = 0
        binary_count = 1  # Host
        for scr in self.screenlist:
            if not self._screen_in_subset(scr):
                continue
            if scr.tabbed:
                screen_count += 1
            elif scr.release:
                binary_count += 1

        if self._subset_screens is not None:
            if not self._subset_screens:
                print("Subset release aborted: no screens selected.", flush=True)
                return
            print(f"Subset release: {len(self._subset_screens)} screen(s) included.",
                  flush=True)

        total = pkg_count + screen_count + binary_count
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

        # Screens (.pyd)
        self._category = "Screens"
        self._cat_index = 0
        self._cat_count = screen_count
        if not self.compile_screens(mode="pyd"):
            self._status("", newline=True)
            print(f"\nRelease FAILED during Screen compilation.", flush=True)
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
        self.clean()

        # Nuitka exes live at the install root and are launched directly.
        # No PyInstaller launcher shim, no .Runtime/ indirection — see #105.
        pendix = self.title if self.flag == "" else f"{self.title}-{self.flag}"
        final = f"{self.location}{pendix}"

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
        StringStruct('OriginalFilename', '{_esc(pendix)}_Installer.exe'),
        StringStruct('ProductName', '{_esc(self.title)}'),
        StringStruct('ProductVersion', '{ver_str}'),
      ])
    ]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
""")

        #%Uninstaller compilation (cached)
        uninstaller_src = VISROOT.replace("\\","/")+"Structures/Uninstaller.py"
        cache_uninstaller = cache_dir + "/uninstaller_base"
        if sys.platform == "win32":
            cache_uninstaller += ".exe"
        uninst_hash_file = cache_dir + "/uninstaller.hash"

        #Hash uninstaller source + icon + version info to detect changes
        uninst_hasher = hashlib.sha256()
        for path in (uninstaller_src, icon_file, version_info_path):
            with open(path, "rb") as f:
                uninst_hasher.update(f.read())
        uninst_current_hash = uninst_hasher.hexdigest()

        #Check if cached uninstaller is still valid
        uninst_cached_hash = ""
        if os.path.exists(uninst_hash_file) and os.path.exists(cache_uninstaller):
            with open(uninst_hash_file, "r") as f:
                uninst_cached_hash = f.read().strip()

        if uninst_cached_hash == uninst_current_hash:
            print("Uninstaller source unchanged — using cached uninstaller", flush=True)
        else:
            print(f"Compiling uninstaller for {pendix}", flush=True)
            subprocess.call(
                f"pyinstaller --noconfirm --onefile "
                f"{'--uac-admin ' if sys.platform == 'win32' else ''}"
                f"--windowed --name Uninstaller --log-level FATAL "
                f"--icon {icon_file} --hidden-import PIL._tkinter_finder "
                f"--version-file {version_info_path} "
                f"{uninstaller_src}",
                shell=True, cwd=self.location
            )

            #Cache the compiled uninstaller
            uninst_results = glob.glob("Uninstaller*", root_dir=self.location+"dist/")
            if not uninst_results:
                print("Build failed: Uninstaller not found in dist/")
                return
            built_uninst = uninst_results[0]
            shutil.copy2(self.location+f"dist/{built_uninst}", cache_uninstaller)

            #Save hash for future comparisons
            with open(uninst_hash_file, "w") as f:
                f.write(uninst_current_hash)

            #Clean PyInstaller build artifacts
            shutil.rmtree(self.location+"dist/", ignore_errors=True)
            shutil.rmtree(self.location+"build/", ignore_errors=True)
            if os.path.exists(self.location+"Uninstaller.spec"):
                os.remove(self.location+"Uninstaller.spec")

            print("Uninstaller cached for future releases", flush=True)

        #Copy uninstaller into build output so it ends up in binaries.zip
        uninst_dest_name = "Uninstaller.exe" if sys.platform == "win32" else "Uninstaller"
        shutil.copy2(cache_uninstaller, f"{final}/{uninst_dest_name}")
        print(f"Uninstaller included in release: {uninst_dest_name}", flush=True)

        #Create binaries.zip from built output
        print(f"Creating binaries.zip from {final} for installer", flush=True)
        shutil.make_archive(base_name=f"{self.location}binaries", format="zip", root_dir=final)

        #%Installer compilation (cached)
        installer_src = VISROOT.replace("\\","/")+"Structures/Installer.py"

        cache_base = cache_dir + "/installer_base"
        if sys.platform == "win32":
            cache_base += ".exe"
        cache_hash_file = cache_dir + "/installer.hash"

        #Hash installer source + icon + version info to detect changes
        hasher = hashlib.sha256()
        for path in (installer_src, icon_file, version_info_path):
            with open(path, "rb") as f:
                hasher.update(f.read())
        current_hash = hasher.hexdigest()

        #Check if cached base installer is still valid
        cached_hash = ""
        if os.path.exists(cache_hash_file) and os.path.exists(cache_base):
            with open(cache_hash_file, "r") as f:
                cached_hash = f.read().strip()

        if cached_hash == current_hash:
            print("Installer source unchanged — using cached base installer", flush=True)
        else:
            print(f"Compiling base installer for {pendix}", flush=True)
            subprocess.call(
                f"pyinstaller --noconfirm --onefile "
                f"{'--uac-admin ' if sys.platform == 'win32' else ''}"
                f"--windowed --name installer_base --log-level FATAL "
                f"--icon {icon_file} --hidden-import PIL._tkinter_finder "
                f"--hidden-import psutil "
                f"--version-file {version_info_path} "
                f"{installer_src}",
                shell=True, cwd=self.location
            )

            #Cache the compiled base installer
            base_results = glob.glob("installer_base*", root_dir=self.location+"dist/")
            if not base_results:
                print("Build failed: installer_base not found in dist/")
                return
            built_base = base_results[0]
            shutil.copy2(self.location+f"dist/{built_base}", cache_base)

            #Save hash for future comparisons
            with open(cache_hash_file, "w") as f:
                f.write(current_hash)

            #Clean PyInstaller build artifacts
            shutil.rmtree(self.location+"dist/", ignore_errors=True)
            shutil.rmtree(self.location+"build/", ignore_errors=True)
            if os.path.exists(self.location+"installer_base.spec"):
                os.remove(self.location+"installer_base.spec")

            print("Base installer cached for future releases", flush=True)

        #Concatenate: cached base exe + binaries.zip = final installer
        installer_name = f"{pendix}_Installer"
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
