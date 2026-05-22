# Session Handoff — Host CLI mode + project commands

**Date:** 2026-05-22
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
- **dev/compiled lock-domain split:** the single-instance port now keys on `title + user + mode`, where mode = `dev`/`compiled` from `Path(sys.executable).name` (python vs the app binary). So a `python .VIS/Host.py` dev Host and a compiled `WOM.exe` run side by side without colliding, and each CLI client routes to its own.

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
- **Compiled (Windows):** CLI roundtrip both sides, two-binary subsystems (2/3), dev (59825) + compiled (60676) Hosts coexisting, each CLI routing to its own. ✓ (from the pre-commands build)
- **Linux (WSL2):** GUI launch daemonizes (terminal freed, Host detached); `ping` foreground roundtrip. ✓
- **commands.pyd (compiled):** ⏳ a `VIS release` is finishing as of this writing — verify `runtime/commands.pyd` exists and compiled `WOM ping` works. The commands compile had a bug (source/copy package collision) fixed in `a70d203` by running Nuitka from the build-copy parent; manual compile of `commands.pyd` succeeded.

---

## Environment / state to restore

- **VIStk install (Windows site-packages):** currently the `serene-rubin` worktree code (this session). Restore master with `pip install C:\Users\bmiCAD\Documents\VIStk` (the main checkout) when done.
- **WSL:** dev venv `~/dev` currently has the `serene-rubin` VIStk; restore via `PYWOM.sh`'s pip lines (installs from `C:\…\Documents\VIStk` = master) or `pip install /mnt/c/.../serene-rubin-9e2c88` to keep this session's code. The `~/wnet` mount is **not persistent** (the `/etc/fstab` line is a note, not a real entry) — remount with `sudo mount -t drvfs '\\192.168.1.34\Library' ~/wnet` (passwordless sudo). `PYWOM.sh` rsyncs pywom to `~/build/PYWOM` before `VIS release -f Linux` (network-drive compile workaround).
- The user installs via the **GUI installer** (quiet is broken, #149). The no-flash two-binary build is installed at `C:\Users\bmiCAD\AppData\Local\bmicad\WOM`.

---

## Remaining TODO (docs + verification — pick up here)

- [x] Verify the compiled `commands.pyd` build (the in-progress `VIS release`) + compiled `WOM ping`. *(Done: rebuilt on Windows; `WOM.com ping` → `pong from Host pid=… open_windows=1`.)*
- [ ] WSL: re-verify `WOM ping` end-to-end with the commands feature (reinstall serene VIStk into `~/dev`).
- [x] Update **issue #144** to the final command model.
- [x] **PYWOM `CLAUDE.md`**: add the `commands/c_*.py` + `_c_<name>` convention to the VIStk conventions section (after "CLI / IPC Args"). It's the synced agent-instructions file. *(Done in `f7416bf`.)*
- [x] **VIStk `changelog.md` + `documentation.md`** (and Sphinx `docs/source` if desired): document the CLI command model, two-binary, dev/compiled split, daemonize. (WOMDOCS just links to VIStk GitHub pages — nothing needed there.) *(changelog 0.5.2 + documentation Host CLI Commands; also de-duplicated changelog and promoted 0.5.1 Screen Isolation to Released.)*
- [x] **PYWOM `changelog.md`**: entry for the `commands/` feature.
- [ ] When ready: merge PR #143 (closes #150/#151/#152), then the pywom commands work is consistent with VIStk master.
