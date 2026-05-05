"""Runtime install-state introspection for VIStk apps.

When a user clicks a navigation button that points at a screen whose binary
was not included in their installer (e.g. the developer built a subset
release, or the user unchecked the group at install time), VIStk shows a
non-blocking banner in the Host's ``InfoRow``. These helpers answer
"is this screen actually on disk?" for that pre-open check.

In dev mode (``sys.frozen`` is falsy) the checks always return ``True`` —
every screen is available from source.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def _install_dir() -> Path | None:
    """Return the install directory when running from a compiled build."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return None


def _screen_script_stem(root: Path, name: str) -> str:
    """Resolve a screen's script stem from the installed ``project.json``.

    Falls back to ``name`` when the project.json is unreadable or doesn't
    list the screen — which preserves the old "name-equals-stem" assumption
    for screens whose script happens to match their registry name.
    """
    try:
        with open(root / ".VIS" / "project.json") as f:
            info = json.load(f)
        title = next(iter(info.keys()))
        scr = info[title].get("Screens", {}).get(name, {})
        script = scr.get("script", "")
        if script:
            stem = script.rsplit("/", 1)[-1]
            stem = stem.rsplit(".", 1)[0]
            return stem or name
    except Exception:
        pass
    return name


def is_screen_installed(name: str, install_dir: Path | None = None) -> bool:
    """Return True if screen ``name`` is present on disk in the installation.

    Dev mode always returns True. For frozen builds the check prefers
    ``.VIS/install_log.json``; when the log doesn't list the screen the
    helper falls through to a direct filesystem probe for the tabbed
    ``Screens/<script_stem>.pyd`` (``.so`` on Linux/macOS) or the
    standalone ``<name>.exe`` artifact at the install root (#105).  The
    legacy ``.Runtime/<name>.exe`` location is also checked for back-
    compat with installations made before #105.

    The fall-through-on-missing behaviour exists because old installers
    only listed user-selectable screens in the log, omitting tabbed ones
    that physically ship with the host bundle (#130).  The filesystem
    probe catches that case.
    """
    root = install_dir or _install_dir()
    if root is None:
        return True  # dev mode — assume every screen is importable from source

    # Step 1: trust the install log when it claims to know the screen.
    log_path = root / ".VIS" / "install_log.json"
    if log_path.exists():
        try:
            with open(log_path) as f:
                log = json.load(f)
            names = {s.get("name") for s in log.get("screens", [])}
            if name in names:
                return True
        except Exception:
            pass  # fall through to filesystem probe

    # Step 2: filesystem probe — covers tabbed screens that older logs
    # silently omitted, plus a sanity check on standalone exes.
    ext = ".exe" if sys.platform == "win32" else ""
    mod_ext = ".pyd" if sys.platform == "win32" else ".so"
    if (root / (name + ext)).exists():
        return True
    stem = _screen_script_stem(root, name)
    if (root / "Screens" / f"{stem}{mod_ext}").exists():
        return True
    if stem != name and (root / "Screens" / f"{name}{mod_ext}").exists():
        return True
    # Legacy layout (pre-#105): standalone exe in .Runtime/
    if (root / ".Runtime" / (name + ext)).exists():
        return True
    return False
