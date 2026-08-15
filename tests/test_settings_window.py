"""Tk smoke + logic tests for the 0.6.0 SettingsWindow.

Builds the real window against a fake host (no .VIS project needed), edits
Tk variables, and exercises Save / Restore Defaults.  Requires a usable Tk
display; skips cleanly if Tk can't initialise.

Run: python tests/test_settings_window.py
"""
import os
import sys
import tempfile
import types

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_failures = []


def check(label, cond):
    print(f"  {'PASS' if cond else 'FAIL'}  {label}")
    if not cond:
        _failures.append(label)


def main():
    try:
        import tkinter as tk
    except Exception as e:
        print(f"SKIP: tkinter unavailable ({e})")
        return

    try:
        root = tk.Tk()
        root.withdraw()
    except Exception as e:
        print(f"SKIP: no Tk display ({e})")
        return

    from VIStk.Structures._Settings import ProjectSettings
    from VIStk.Widgets._SettingsWindow import SettingsWindow

    d = tempfile.mkdtemp()
    settings = ProjectSettings(types.SimpleNamespace(
        p_settings=os.path.join(d, "settings.json")))

    startup_calls = []
    panel_called = {"hit": False}

    def dev_panel(frame):
        panel_called["hit"] = True
        tk.Label(frame, text="custom").pack()

    # The Appearance tab reads the project's palette registry (0.6.5).  Those
    # are Project classmethods over process-wide state, so the stub can borrow
    # them directly while keeping its own throwaway Settings.
    from VIStk.Structures._Project import Project
    host = types.SimpleNamespace(
        Project=types.SimpleNamespace(
            title="TestApp", Settings=settings,
            offeredPalettes=Project.offeredPalettes,
            defaultPalette=Project.defaultPalette,
            setActivePalette=Project.setActivePalette,
            activePalette=Project.activePalette),
        _settings_panels={"My Plugin": dev_panel},
        _register_startup=lambda: startup_calls.append("register"),
        unregister_startup=lambda: startup_calls.append("unregister"),
        _watch_system_theme=lambda: None,
    )

    print("build:")
    win = SettingsWindow(host, parent=None)  # builds, does not block (no show())
    check("seeds a var for every DEFAULTS-backed control",
          "notifications.duration_ms" in win._vars
          and "window.remember_geometry" in win._vars
          and "appearance.font_family" in win._vars)
    check("dev-registered panel setup_fn invoked", panel_called["hit"] is True)
    check("duration seeded from default (5000)",
          win._vars["notifications.duration_ms"][0].get() == "5000")
    check("font family seeded blank (None default)",
          win._vars["appearance.font_family"][0].get() == "")

    print("negative-int coercion (typed past Spinbox from_=0):")
    var, vtype = win._vars["window.default_width"]
    var.set("-50")
    check("negative int -> None (rejected)", win._coerce("window.default_width", var, vtype) is None)
    var.set("900")
    check("positive int -> int", win._coerce("window.default_width", var, vtype) == 900)
    var.set("")
    check("blank int -> None", win._coerce("window.default_width", var, vtype) is None)
    var.set("900")  # restore non-default so _save below behaves predictably

    print("edit + save (overrides-only + startup reconcile):")
    win._vars["notifications.duration_ms"][0].set("3000")
    win._vars["window.remember_geometry"][0].set(True)
    win._vars["host.start_with_os"][0].set(True)
    # leave notifications.enabled at its default (True) -> must NOT be stored
    win._save()  # writes, reconciles startup, destroys window

    reloaded = ProjectSettings(types.SimpleNamespace(
        p_settings=os.path.join(d, "settings.json")))
    check("changed int persisted", reloaded.get("notifications.duration_ms") == 3000)
    check("changed bool persisted", reloaded.get("window.remember_geometry") is True)
    check("unchanged default NOT stored (overrides-only)",
          "notifications.enabled" not in reloaded)
    check("start_with_os toggle reconciled to register", startup_calls == ["register"])

    print("blank int -> None; restore defaults:")
    win2 = SettingsWindow(host, parent=None)
    win2._vars["notifications.duration_ms"][0].set("")  # blank
    win2._restore_defaults()
    check("restore_defaults resets duration var to default",
          win2._vars["notifications.duration_ms"][0].get() == "5000")
    check("restore_defaults clears font family var",
          win2._vars["appearance.font_family"][0].get() == "")
    # blank an int and save -> stored/reset appropriately
    win2._vars["window.default_width"][0].set("")  # blank -> None == default -> reset
    win2._vars["host.start_with_os"][0].set(False)
    win2._save()
    reloaded2 = ProjectSettings(types.SimpleNamespace(
        p_settings=os.path.join(d, "settings.json")))
    check("blank int equals default -> not stored",
          "window.default_width" not in reloaded2)
    check("start_with_os off -> unregister called",
          startup_calls == ["register", "unregister"])

    print("appearance apply-on-launch:")
    import tkinter.font as tkfont
    from VIStk.Objects._Host import Host
    appear_settings = ProjectSettings(types.SimpleNamespace(
        p_settings=os.path.join(tempfile.mkdtemp(), "settings.json")))
    appear_settings.set("appearance.font_family", "Courier New")
    appear_settings.set("appearance.font_size", 13)
    appear_host = types.SimpleNamespace(
        Project=types.SimpleNamespace(Settings=appear_settings))
    Host._apply_appearance(appear_host)
    df = tkfont.nametofont("TkDefaultFont")
    check("apply_appearance sets named-font family",
          df.actual("family") == "Courier New")
    check("apply_appearance sets named-font size", df.actual("size") == 13)

    # No appearance settings -> no-op (must not raise).
    noop_settings = ProjectSettings(types.SimpleNamespace(
        p_settings=os.path.join(tempfile.mkdtemp(), "settings.json")))
    Host._apply_appearance(types.SimpleNamespace(
        Project=types.SimpleNamespace(Settings=noop_settings)))
    check("apply_appearance no-op when unset (no raise)", True)

    try:
        root.destroy()
    except Exception:
        pass

    print()
    if _failures:
        print(f"{len(_failures)} FAILED: {_failures}")
        sys.exit(1)
    print("ALL PASSED")


if __name__ == "__main__":
    main()
