"""Logic tests for the 0.6.0 session persistence / restore wiring.

Exercises the real Host / DetachedWindow methods against lightweight fakes
(the framework-source repo has no .VIS/project.json, so the real Host/Project
can't be instantiated here).

Run: python tests/test_session_restore.py
"""
import os
import sys
import tempfile
import types

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from VIStk.Objects._Host import Host
from VIStk.Objects._DetachedWindow import DetachedWindow
from VIStk.Structures._Settings import ProjectSettings


_failures = []


def check(label, cond):
    print(f"  {'PASS' if cond else 'FAIL'}  {label}")
    if not cond:
        _failures.append(label)


# ── Fakes ─────────────────────────────────────────────────────────────────────

def make_tm(base_names):
    tm = types.SimpleNamespace()
    tm._tabs = {i: {"base_name": b} for i, b in enumerate(base_names)}
    return tm


def make_window(*panes_base_names, geometry="800x600+10+20"):
    """A fake DetachedWindow: one SplitView whose panes carry the given tabs."""
    tms = [make_tm(bn) for bn in panes_base_names]
    sv = types.SimpleNamespace(all_tab_managers=lambda: tms)
    win = types.SimpleNamespace(geometry=lambda: geometry)
    return types.SimpleNamespace(_split_view=sv, win=win)


def make_settings():
    d = tempfile.mkdtemp()
    proj = types.SimpleNamespace(p_settings=os.path.join(d, "settings.json"))
    return ProjectSettings(proj)


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_snapshot_open_tabs():
    print("Host._snapshot_open_tabs:")
    w1 = make_window(["A", "B"])          # one pane, two tabs
    w2 = make_window(["C"], ["D", "E"])   # two panes
    host = types.SimpleNamespace(detached_windows=[w1, w2])
    out = Host._snapshot_open_tabs(host)
    check("walks all windows/panes/tabs in order", out == ["A", "B", "C", "D", "E"])

    host2 = types.SimpleNamespace(detached_windows=[])
    check("no windows -> empty list", Host._snapshot_open_tabs(host2) == [])


def test_persist_session():
    print("Host._persist_session:")
    s = make_settings()
    w = make_window(["A", "B"], geometry="1024x768+5+5")
    host = types.SimpleNamespace(
        Project=types.SimpleNamespace(Settings=s),
        detached_windows=[w], _primary_window=w,
    )
    # Bind the real collaborator methods so _persist_session (which now
    # delegates to _capture_session + _commit_session) is genuinely exercised
    # rather than swallowed by its try/except.
    host._snapshot_open_tabs = lambda: Host._snapshot_open_tabs(host)
    host._capture_session = lambda *a, **k: Host._capture_session(host, *a, **k)
    host._commit_session = lambda cap: Host._commit_session(host, cap)

    # Both toggles off -> nothing written.
    Host._persist_session(host, open_tabs=["X", "Y"], geo_window=w)
    check("toggles off -> no last_tabs override", "host.last_tabs" not in s)
    check("toggles off -> no last_geometry override", "window.last_geometry" not in s)

    # remember_tabs on -> tabs stored from explicit capture.
    s.set("host.remember_tabs", True)
    Host._persist_session(host, open_tabs=["X", "Y"], geo_window=w)
    check("remember_tabs -> stores explicit open_tabs", s.get("host.last_tabs") == ["X", "Y"])

    # open_tabs=None -> live snapshot of all windows (w carries A,B).  Reset
    # first so a pass can't ride on the explicit value just stored above.
    s.reset("host.last_tabs")
    Host._persist_session(host, open_tabs=None, geo_window=w)
    check("remember_tabs + open_tabs=None -> live snapshot",
          s.get("host.last_tabs") == ["A", "B"])

    # remember_geometry on -> geometry captured from window.
    s.set("window.remember_geometry", True)
    Host._persist_session(host, open_tabs=["A"], geo_window=w)
    check("remember_geometry -> stores win.geometry()",
          s.get("window.last_geometry") == "1024x768+5+5")

    # geo_window=None falls back to _primary_window.
    s.reset("window.last_geometry")
    Host._persist_session(host, open_tabs=["A"], geo_window=None)
    check("geo_window=None -> uses _primary_window",
          s.get("window.last_geometry") == "1024x768+5+5")

    # Primary window not in detached_windows (already closed) -> no geometry.
    s.reset("window.last_geometry")
    host.detached_windows = []
    Host._persist_session(host, open_tabs=["A"], geo_window=None)
    check("primary already closed -> geometry skipped", "window.last_geometry" not in s)


def test_open_startup():
    print("Host._open_startup priority:")

    def make_host(startup_screen=None, startup_args=None, remember=False,
                  last_tabs=None, installed=(), default=None):
        s = make_settings()
        s.set("host.remember_tabs", remember)
        if last_tabs is not None:
            s.set("host.last_tabs", last_tabs)
        installed_set = set(installed)
        proj = types.SimpleNamespace(
            Settings=s,
            default_screen=default,
            getScreen=lambda name: object() if name in installed_set else None,
        )
        calls = []
        host = types.SimpleNamespace(
            _startup_screen=startup_screen, _startup_args=startup_args,
            Project=proj, open=lambda name, args=None: calls.append((name, args)),
        )
        return host, calls

    # 1. Explicit CLI screen wins, with args, restore skipped.
    host, calls = make_host(startup_screen="Editor", startup_args=["--won", "9"],
                            remember=True, last_tabs=["A"], installed=("A", "Editor"))
    Host._open_startup(host)
    check("explicit CLI screen opened with args", calls == [("Editor", ["--won", "9"])])

    # 2. remember_tabs restores installed screens, drops missing, skips default.
    host, calls = make_host(remember=True, last_tabs=["A", "GONE", "B"],
                            installed=("A", "B"), default="Home")
    Host._open_startup(host)
    check("restores installed tabs only, in order",
          calls == [("A", None), ("B", None)])

    # 3. remember off -> default screen.
    host, calls = make_host(remember=False, default="Home", installed=("Home",))
    Host._open_startup(host)
    check("remember off -> default screen", calls == [("Home", None)])

    # 4. remember on but no saved tabs -> default screen.
    host, calls = make_host(remember=True, last_tabs=[], default="Home")
    Host._open_startup(host)
    check("remember on, empty last_tabs -> default", calls == [("Home", None)])

    # 5. remember on but all saved screens uninstalled -> default screen.
    host, calls = make_host(remember=True, last_tabs=["X", "Y"], installed=(),
                            default="Home")
    Host._open_startup(host)
    check("remember on, all uninstalled -> default", calls == [("Home", None)])

    # 6. nothing to open -> no calls (idle Host).
    host, calls = make_host(remember=False, default=None)
    Host._open_startup(host)
    check("no startup/default -> no open", calls == [])


def test_detached_helpers():
    print("DetachedWindow helpers:")
    dw = make_window(["A", "B"], ["C"])
    check("_snapshot_base_names walks all panes",
          DetachedWindow._snapshot_base_names(dw) == ["A", "B", "C"])

    fake = types.SimpleNamespace(win=types.SimpleNamespace(
        winfo_screenwidth=lambda: 1920, winfo_screenheight=lambda: 1080))
    check("_aligned_xy center", DetachedWindow._aligned_xy(fake, 1200, 800, "center")
          == ((1920 - 1200) // 2, (1080 - 800) // 2))
    check("_aligned_xy nw", DetachedWindow._aligned_xy(fake, 1200, 800, "nw") == (0, 0))
    check("_aligned_xy se", DetachedWindow._aligned_xy(fake, 1200, 800, "se")
          == (1920 - 1200, 1080 - 800))
    check("_aligned_xy unknown -> center", DetachedWindow._aligned_xy(fake, 1200, 800, "zzz")
          == ((1920 - 1200) // 2, (1080 - 800) // 2))


def test_capture_commit():
    print("Host._capture_session / _commit_session (veto-safety):")
    s = make_settings()
    w = make_window(["A", "B"], geometry="640x480+1+2")
    host = types.SimpleNamespace(
        Project=types.SimpleNamespace(Settings=s),
        detached_windows=[w], _primary_window=w)
    host._snapshot_open_tabs = lambda: Host._snapshot_open_tabs(host)

    # Capture must be a pure read: no settings written (the quit_host
    # pre-close snapshot that a veto must be able to discard).
    cap = Host._capture_session(host)
    check("toggles off -> empty capture", cap == {})
    check("capture does not dirty settings", s.dirty is False)

    s.set("host.remember_tabs", True)
    s.set("window.remember_geometry", True)
    s.save()  # clear dirty after enabling toggles
    cap = Host._capture_session(host)
    check("captures tabs from live windows", cap.get("tabs") == ["A", "B"])
    check("captures geometry from primary window", cap.get("geometry") == "640x480+1+2")
    check("capture still writes nothing (not dirty)", s.dirty is False)
    check("veto-safety: uncommitted capture -> last_tabs absent",
          "host.last_tabs" not in s)

    Host._commit_session(host, cap)
    check("commit writes tabs", s.get("host.last_tabs") == ["A", "B"])
    check("commit writes geometry", s.get("window.last_geometry") == "640x480+1+2")
    check("commit dirties settings", s.dirty is True)


def main():
    test_snapshot_open_tabs()
    test_persist_session()
    test_capture_commit()
    test_open_startup()
    test_detached_helpers()
    print()
    if _failures:
        print(f"{len(_failures)} FAILED: {_failures}")
        sys.exit(1)
    print("ALL PASSED")


if __name__ == "__main__":
    main()
