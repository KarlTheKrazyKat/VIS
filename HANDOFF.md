# Session Handoff — Host CLI mode + project commands

**Date:** 2026-05-22 (cont. 2026-05-23: `is_compiled()` fix + compiled verification from arbitrary CWD)
**Branch (VIStk):** `host-single-instance` (PR #143, KarlTheKrazyKat/VIS) — **open, do not merge yet**
**Repo (project):** KarlTheKrazyKat/PYWOM `master`
**Resume on another box:** `git fetch && git checkout host-single-instance` (VIStk) + pull PYWOM `master`. Everything is on GitHub.

---

## What this session built

A non-GUI **CLI command** path for the always-Host model, plus the cross-platform packaging to support it.

### Command model (final)
- Invoke as a **bare subcommand**: `WOM ping` (not `--ping`).
- A command is a file: **`<project>/commands/c_<name>.py`** with an entry **`_c_<name>(args)`** (mirrors the `_m_<name>` convention).
- `_c_<name>(args)` runs **on the running Host**, and returns a `(callable, args)` **continuation** for the terminal side (or `None`). `args` is the list of words after the command name.
- Discovery: **`commands.__all__`** is the manifest — built dynamically in dev (`commands/__init__.py` scans `c_*.py`), and baked **static** into `commands.pyd` by `VIS release`.
- Resolution: the Host imports `commands.c_<name>` lazily and reads `commands.__all__` for usage errors. Screens win over commands (screen registry checked first).
- VIStk ships **no** commands — `_cli.py` is transport + the generic `print_line` terminal helper only.

### Architecture (continuation-passing two-pump)
- Two roles, same shape: **H** (running Host, Tk loop) and **T** (terminal-launched instance). Each has a queue, a pump, and a socket bridge.
- Continuations cross the socket **by reference** (`module:qualname`, re-imported on the far side — both ends are the same binary). Closures can't cross; args must be JSON-serializable.
- Reply invariant: every message gets exactly one response over its channel; T exits when its queue is empty and no request is outstanding.
- H-side functions must NOT block (Tk loop); T-side may block (`input()`).

### Cross-platform packaging
- **Windows two-binary:** `WOM.exe` (PE subsystem 2 = GUI, no console flash) + `WOM.com` (subsystem 3 = console, shell waits + stdio). Built by copying the exe and patching the PE subsystem byte (`_Release._patch_pe_subsystem`). Typed `wom` resolves to `.com` via PATHEXT.
- **Linux daemonize:** a GUI launch `fork`+`setsid`s so the terminal is freed and the Host runs detached; CLI commands stay foreground. (`Host._daemonize`, guarded `sys.platform != "win32"`.)
- **dev/compiled lock-domain split:** the single-instance port now keys on `title + user + mode`, where mode = `dev`/`compiled` (via `is_compiled()`, below). So a `python .VIS/Host.py` dev Host and a compiled `WOM.exe` run side by side without colliding, and each CLI client routes to its own.
- **Compiled-mode detection fix (`is_compiled()`, commit `0ba0a16`):** Nuitka `--standalone` (what VIS ships) does NOT set `sys.frozen`, so `getPath()` fell back to `os.getcwd()` — a compiled Host or CLI command launched from any directory without the project's `.VIS/` returned `None` and the Host entry script died on `import modules.*` before it could route. CLI is always typed from an arbitrary CWD, so this blocked the whole feature in release builds (the GUI dodged it only because shortcuts set "Start in"). Fixed with one `_VINFO.is_compiled()` helper (executable basename: `python*` ⇒ dev) routed through `getPath`, `Host._compute_lock_port`, `Host._register_startup`, `Screen.load`, and the `host.txt` template — single source of truth, replacing the `sys.frozen` checks that misfire under `--standalone`.

---

## Commits on `host-single-instance` (this session, in order)

| Commit | What |
|---|---|
| `9f304e7` | Host CLI mode: continuation-passing two-pump + (original) `--ping` |
| `8e9ee02` | `six` single-file shared-module fix + two-binary `.com` packaging |
| `c65e54b` | Single-instance: dev/compiled lock domains |
| `3f348c7` | Linux: daemonize the primary GUI Host |
| `3e82919` | CLI: bare-subcommand format (`WOM ping`, not `--ping`) |
| `a70d203` | CLI commands: project-defined `commands/c_*.py`, drop built-in ping; `_Release.compile_commands()` -> `commands.pyd` |
| `0ba0a16` | `is_compiled()` helper: detect compiled mode by exe name (not `sys.frozen`) — fixes CLI from arbitrary CWD under Nuitka `--standalone`; consolidates the dev/compiled split |
| `9ff6655` | CLI runs **headless** when no Host is up (`Host._cli_run_local`) instead of launching the GUI — the command still executes in-process (`_HOST_INSTANCE` None ⇒ graceful degrade) |
| `b7329b5` | Installer: stop creating the legacy empty hidden `.Runtime` dir (no per-screen exes under always-Host) — `.VIS` stays hidden (getPath needs `runtime/.VIS/project.json`) |
| `4543936` | Uninstaller: read `install_log.json` + assets from the `runtime/` layout (was probing the install root → "no install_log.json found") |
| `b7c50db` → reverted by `29817c1` | (Tried adding `release=true` tabbed screens to Start Menu shortcuts; **reverted** — Landing is the default screen, already opened by the main-app shortcut, so a Landing shortcut is redundant. Original `selected_screens` loop is correct: main app + release standalones = WOM, AssetManager, FloorView.) |
| `f47856d` | Installer: **also** drop the launcher set (WOM/AssetManager/FloorView) in the install root via `shortcut(install_root=True)` — additive, Start Menu + desktop opt-in unchanged; uninstaller's install-root sweep removes them |

PYWOM `master`: **`a71ffef`** — `commands/__init__.py` + sample `commands/c_ping.py`.

---

## Issues (KarlTheKrazyKat/VIS)

- **#144** Host CLI mode — design. **NEEDS UPDATE** to the final model (subcommand + `commands/c_*.py` + `_c_<name>` + `commands.pyd`); currently the symmetric two-pump draft, pre-rename.
- **#149** Quiet installer (`--Quiet`) exits without extracting — its own status-verification bug (not ours). GUI installer is the workaround.
- **#150** `compile_shared` shipped all of site-packages for single-file modules (six) — FIXED by `8e9ee02`; close on merge.
- **#151** dev/compiled lock-domain split — done (`c65e54b`).
- **#152** Linux daemonize — done (`3f348c7`); verified in WSL.

---

## Verification status

- **Dev (Windows source):** `WOM ping` -> `pong from Host pid=…`; unknown command -> usage error listing known commands. ✓
- **Compiled (Windows):** Full rebuild (13m, exit 0) with `commands.pyd` + the `is_compiled()` fix, installed by extracting `dist/binaries.zip` to the install dir (mimics the GUI installer). GUI `WOM.exe` primary launched **from `C:\`** (no project `.VIS` in CWD), bound lock port 60676; `WOM.com ping` → `pong from Host pid=… open_windows=1`; unknown command → `WOM: unrecognized command: … / known commands: ping`. Two-binary subsystems 2/3. **All from an arbitrary CWD** — the pre-fix build crashed here on `import modules.menu`. ✓
- **Compiled (Windows) — no-Host CLI (`9ff6655`):** with no Host running, `WOM.com ping` from `C:\` → `pong … open_windows=0`, returns immediately, **no GUI / no lingering process** (was launching the GUI); unknown command → usage error; and with a GUI host up, `WOM.com ping` → remote `open_windows=1` (host-running path intact). ✓
- **Linux (WSL2):** GUI launch daemonizes (terminal freed, Host detached); `ping` foreground roundtrip. ✓
- **commands.pyd (compiled):** ⏳ a `VIS release` is finishing as of this writing — verify `runtime/commands.pyd` exists and compiled `WOM ping` works. The commands compile had a bug (source/copy package collision) fixed in `a70d203` by running Nuitka from the build-copy parent; manual compile of `commands.pyd` succeeded.

---

## Environment / state to restore

- **VIStk install (Windows site-packages):** currently the `serene-rubin` worktree code (this session). Restore master with `pip install C:\Users\bmiCAD\Documents\VIStk` (the main checkout) when done.
- **WSL:** dev venv `~/dev` currently has the `serene-rubin` VIStk; restore via `PYWOM.sh`'s pip lines (installs from `C:\…\Documents\VIStk` = master) or `pip install /mnt/c/.../serene-rubin-9e2c88` to keep this session's code. The `~/wnet` mount is **not persistent** (the `/etc/fstab` line is a note, not a real entry) — remount with `sudo mount -t drvfs '\\192.168.1.34\Library' ~/wnet` (passwordless sudo). `PYWOM.sh` rsyncs pywom to `~/build/PYWOM` before `VIS release -f Linux` (network-drive compile workaround).
- The user installs via the **GUI installer** (quiet is broken, #149). The no-flash two-binary build is installed at `C:\Users\bmiCAD\AppData\Local\bmicad\WOM`.
- **Latest installer (2026-05-25):** `~/Downloads/WOM-Windows_Installer.exe` is the current build — `is_compiled()` + headless no-Host CLI + install-layout fixes (no `.Runtime`; `runtime/`-aware uninstaller; Start Menu shortcuts = WOM/AssetManager/FloorView, **no Landing**). The runtime Nuitka binaries are from the 2026-05-23 `VIS release`; the installer + uninstaller exes were rebuilt via the `_build_installer` fast path (Installer.py/Uninstaller.py only, no Nuitka recompile). Run it for a clean GUI reinstall + uninstall test. (The install dir `…\bmicad\WOM` still holds a manual `binaries.zip` extraction used for the compiled CLI tests — not a real install.)
- **Local hook note (this machine only):** the user-settings `PostToolUse` skill-suggestion hook was converted from a `prompt` type to a command hook (`~/.claude/hooks/skill_hint.py`) so it stays silent on non-`.py` edits (was halting the turn on every doc/config edit). Backup at `~/.claude/settings.json.bak`. Not repo state.

---

## Remaining TODO (docs + verification — pick up here)

- [x] Verify the compiled `commands.pyd` build (the in-progress `VIS release`) + compiled `WOM ping`. *(Done: rebuilt on Windows; `WOM.com ping` → `pong from Host pid=… open_windows=1`.)*
- [ ] WSL: re-verify `WOM ping` end-to-end with the commands feature (reinstall fixed VIStk into `~/dev`). **Deferred to manual testing (2026-05-23).** `is_compiled()` is platform-agnostic and Windows-compiled is verified from an arbitrary CWD; Linux is correct-by-construction (`python3`⇒dev, `WOM`⇒compiled). WSL env as of probe: `~/dev` venv present, `~/wnet` not mounted, no `~/build/PYWOM` yet.
- [x] Update **issue #144** to the final command model.
- [x] **PYWOM `CLAUDE.md`**: add the `commands/c_*.py` + `_c_<name>` convention to the VIStk conventions section (after "CLI / IPC Args"). It's the synced agent-instructions file. *(Done in `f7416bf`.)*
- [x] **VIStk `changelog.md` + `documentation.md`** (and Sphinx `docs/source` if desired): document the CLI command model, two-binary, dev/compiled split, daemonize. (WOMDOCS just links to VIStk GitHub pages — nothing needed there.) *(changelog 0.5.2 + documentation Host CLI Commands; also de-duplicated changelog and promoted 0.5.1 Screen Isolation to Released.)*
- [x] **PYWOM `changelog.md`**: entry for the `commands/` feature.
- [ ] When ready: merge PR #143 (closes #150/#151/#152), then the pywom commands work is consistent with VIStk master.
