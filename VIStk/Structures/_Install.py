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


def is_screen_installed(name: str, install_dir: Path | None = None) -> bool:
    """Return True if screen ``name`` is present on disk in the installation.

    Dev mode always returns True. For frozen builds the check prefers
    ``.VIS/install_log.json``; when the log is missing or stale the helper
    falls back to a direct filesystem check for the tabbed ``Screens/<name>.pyd``
    or standalone ``.Runtime/<name>.exe`` artifact.
    """
    root = install_dir or _install_dir()
    if root is None:
        return True  # dev mode — assume every screen is importable from source

    log_path = root / ".VIS" / "install_log.json"
    if log_path.exists():
        try:
            with open(log_path) as f:
                log = json.load(f)
            names = {s.get("name") for s in log.get("screens", [])}
            if names:
                return name in names
        except Exception:
            pass  # fall through to filesystem check

    ext = ".exe" if sys.platform == "win32" else ""
    if (root / ".Runtime" / (name + ext)).exists():
        return True
    if (root / "Screens" / f"{name}.pyd").exists():
        return True
    return False
