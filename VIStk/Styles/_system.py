"""OS theme detection — what ``"system"`` means for a palette.

:func:`os_scheme` reports the operating system's light/dark preference, and
:func:`watch` polls it so a palette set to ``"system"`` follows the OS while
the app is running.  Every path is best-effort: an OS that can't be asked (or
answers with something unexpected) reports ``"light"`` rather than raising —
appearance must never block a window from opening.

Detection per platform:

* **Windows** — ``HKCU\\...\\Themes\\Personalize\\AppsUseLightTheme`` (0 = dark).
* **macOS** — ``defaults read -g AppleInterfaceStyle`` (``Dark`` when set).
* **Linux** — the XDG desktop-portal ``color-scheme`` preference via
  ``gsettings``, falling back to the GTK theme name containing ``dark``.
"""
from __future__ import annotations

import subprocess
import sys

__all__ = ["os_scheme", "watch", "unwatch"]

#: How often :func:`watch` re-asks the OS.  A theme switch is a deliberate,
#: rare user action, so this trades latency for staying off the CPU.
POLL_MS = 4000

_last: str | None = None
_watchers: dict[int, str] = {}   # widget id -> pending `after` id


def _windows_scheme() -> str | None:
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize")
        try:
            value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
        finally:
            winreg.CloseKey(key)
        return "light" if int(value) else "dark"
    except Exception:
        return None


def _run(cmd) -> str | None:
    """Run *cmd* and return its stripped stdout, or ``None`` on any failure.

    ``creationflags`` keeps a console from flashing on Windows; the flag does
    not exist on other platforms, hence the guarded lookup.
    """
    try:
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=2,
                             creationflags=flags)
        return out.stdout.strip() or None
    except Exception:
        return None


def _macos_scheme() -> str | None:
    # The key is absent entirely in light mode, which is a non-zero exit.
    out = _run(["defaults", "read", "-g", "AppleInterfaceStyle"])
    return "dark" if out and "dark" in out.lower() else "light"


def _linux_scheme() -> str | None:
    out = _run(["gsettings", "get", "org.gnome.desktop.interface", "color-scheme"])
    if out:
        low = out.lower()
        if "dark" in low:
            return "dark"
        if "light" in low or "default" in low:
            return "light"
    out = _run(["gsettings", "get", "org.gnome.desktop.interface", "gtk-theme"])
    if out:
        return "dark" if "dark" in out.lower() else "light"
    return None


def os_scheme() -> str:
    """The OS light/dark preference — ``"light"`` or ``"dark"``.

    Falls back to ``"light"`` on any platform that can't be asked.
    """
    if sys.platform == "win32":
        scheme = _windows_scheme()
    elif sys.platform == "darwin":
        scheme = _macos_scheme()
    else:
        scheme = _linux_scheme()
    return scheme if scheme in ("light", "dark") else "light"


def watch(widget, on_change) -> None:
    """Poll the OS preference on *widget*'s event loop, calling *on_change*.

    *on_change* receives the new scheme name each time it changes — never on
    the first poll, which only records the starting value.  Re-registering for
    the same widget replaces the previous watch, so a rebuilt window doesn't
    stack duplicate pollers.  Stops on its own once the widget is gone.
    """
    global _last
    unwatch(widget)
    if _last is None:
        _last = os_scheme()

    def poll():
        global _last
        try:
            if not widget.winfo_exists():
                _watchers.pop(id(widget), None)
                return
        except Exception:
            _watchers.pop(id(widget), None)
            return
        current = os_scheme()
        if current != _last:
            _last = current
            try:
                on_change(current)
            except Exception:
                import traceback
                traceback.print_exc()
        try:
            _watchers[id(widget)] = widget.after(POLL_MS, poll)
        except Exception:
            _watchers.pop(id(widget), None)

    try:
        _watchers[id(widget)] = widget.after(POLL_MS, poll)
    except Exception:
        pass


def unwatch(widget) -> None:
    """Cancel the poll registered for *widget*, if any."""
    pending = _watchers.pop(id(widget), None)
    if pending is not None:
        try:
            widget.after_cancel(pending)
        except Exception:
            pass
