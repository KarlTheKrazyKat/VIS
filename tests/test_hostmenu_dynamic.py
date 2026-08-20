"""Tests for dynamic (callable) cascade items on HostMenu — issue #193.

A cascade's ``items`` may be a zero-arg callable returning the usual item
spec list.  The submenu is wired to Tk's native ``postcommand`` and rebuilt
from the callable each time it is posted, so it can reflect state that
changed after the Host started.

Run: python tests/test_hostmenu_dynamic.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_failures = []


def check(label, cond):
    print(f"  {'PASS' if cond else 'FAIL'}  {label}")
    if not cond:
        _failures.append(label)


def entries(menu):
    """Labels of every entry in *menu*, separators as ``None``."""
    end = menu.index("end")
    if end is None:
        return []
    out = []
    for i in range(end + 1):
        if menu.type(i) == "separator":
            out.append(None)
        else:
            out.append(menu.entrycget(i, "label"))
    return out


def submenu(menu, label):
    """The Menu widget behind cascade *label* of *menu*."""
    return menu.nametowidget(menu.entrycget(label, "menu"))


def post(menu):
    """Fire the menu's postcommand the way Tk does when it opens."""
    cmd = menu.cget("postcommand")
    if cmd:
        menu.tk.call(cmd)


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

    from VIStk.Widgets._HostMenu import HostMenu

    hm = HostMenu(root)
    hm.attach()

    # State that changes *after* the menu is built.
    recent = ["W21930"]

    def recent_items():
        return [{"label": n, "command": lambda n=n: None} for n in recent]

    print("\n-- screen layer: dynamic submenu --")
    hm.set_screen_items([
        {"label": "Static", "items": [{"label": "One", "command": None}]},
        {"label": "Open Recent", "items": recent_items},
    ], label="File")
    file_menu = submenu(hm.menubar, "File")
    dyn = submenu(file_menu, "Open Recent")

    check("seeded at build time (Windows never posts an empty menu)",
          entries(dyn) == ["W21930"])

    recent.append("W21931")
    check("stale until posted", entries(dyn) == ["W21930"])
    post(dyn)
    check("reflects post-startup state once posted",
          entries(dyn) == ["W21930", "W21931"])

    recent[:] = ["W22000"]
    post(dyn)
    check("repopulates rather than appending", entries(dyn) == ["W22000"])

    print("\n-- static submenus unchanged --")
    stat = submenu(file_menu, "Static")
    check("static submenu still populated", entries(stat) == ["One"])
    check("static submenu has no postcommand", not stat.cget("postcommand"))

    print("\n-- empty result --")
    recent[:] = []
    post(dyn)
    check("empty renders one entry, not an empty panel", len(entries(dyn)) == 1)
    check("placeholder is disabled", dyn.entrycget(0, "state") == "disabled")
    check("default placeholder label", entries(dyn) == ["(empty)"])
    check("placeholder does nothing", not dyn.entrycget(0, "command"))
    recent[:] = ["W22000"]
    post(dyn)
    check("recovers from empty", entries(dyn) == ["W22000"])

    print("\n-- custom empty_label --")
    hm.clear_screen_items()
    hm.set_screen_items([
        {"label": "Recent", "items": lambda: [], "empty_label": "No recent files"},
    ], label="Jump")
    empty = submenu(submenu(hm.menubar, "Jump"), "Recent")
    check("empty_label honoured", entries(empty) == ["No recent files"])
    hm.clear_screen_items()

    print("\n-- nested + separators inside a dynamic result --")
    hm.set_screen_items([
        {"label": "Deep", "items": lambda: [
            {"label": "A", "command": None},
            {"separator": True},
            {"label": "More", "items": [{"label": "B", "command": None}]},
        ]},
    ], label="Nest")
    deep = submenu(submenu(hm.menubar, "Nest"), "Deep")
    post(deep)
    check("separator and nested cascade survive repopulation",
          entries(deep) == ["A", None, "More"])
    check("nested static cascade rebuilt too",
          entries(submenu(deep, "More")) == ["B"])
    hm.clear_screen_items()

    print("\n-- project layer --")
    proj = ["P1"]
    hm.set_project_items([
        {"label": "Recent", "items": lambda: [
            {"label": n, "command": None} for n in proj]},
    ], label="Proj")
    proj_dyn = submenu(submenu(hm.menubar, "Proj"), "Recent")
    proj.append("P2")
    post(proj_dyn)
    check("project-layer dynamic submenu works", entries(proj_dyn) == ["P1", "P2"])
    hm.clear_project_items()

    print("\n-- shared layer (build_shared_menu) --")
    shared = ["S1"]

    def shared_items():
        return [{"label": n, "command": None} for n in shared]

    hm.build_shared_menu({
        "File": [
            {"label": "Open...", "command": None, "state": "disabled"},
            {"separator": True},
            {"label": "Open Recent", "items": shared_items},
        ],
        "Recent": shared_items,          # whole cascade dynamic
    })
    sh_file = hm._shared_menus["File"]
    sh_dyn = submenu(sh_file, "Open Recent")
    shared.append("S2")
    post(sh_dyn)
    check("shared-layer dynamic submenu works", entries(sh_dyn) == ["S1", "S2"])

    sh_cascade = hm._shared_menus["Recent"]
    post(sh_cascade)
    check("whole cascade may be dynamic", entries(sh_cascade) == ["S1", "S2"])

    print("\n-- survives screen replace / restore --")
    hm.save_defaults()
    hm.set_screen_items([{"label": "Export", "command": None}], label="File")
    check("shared File hidden while screen owns the label",
          entries(submenu(hm.menubar, "File")) == ["Export"])
    hm.clear_screen_items()
    restored = submenu(hm.menubar, "File")
    check("shared File restored", entries(restored) == ["Open...", None, "Open Recent"])
    shared[:] = ["S3"]
    post(submenu(restored, "Open Recent"))
    check("still dynamic after restore",
          entries(submenu(restored, "Open Recent")) == ["S3"])

    print("\n-- leaf overrides still work alongside --")
    hm.apply_overrides({"File": {"Open...": {"state": "normal"}}})
    check("override applied", sh_file.entrycget("Open...", "state") == "normal")
    hm.reset_overrides()
    check("override reset", sh_file.entrycget("Open...", "state") == "disabled")

    print("\n-- a raising factory keeps the last good entries --")
    boom = {"fail": False}

    def flaky():
        if boom["fail"]:
            raise RuntimeError("expected — traceback above is part of the test")
        return [{"label": "OK", "command": None}]

    hm.set_screen_items([{"label": "Flaky", "items": flaky}], label="Risk")
    risk = submenu(submenu(hm.menubar, "Risk"), "Flaky")
    boom["fail"] = True
    post(risk)
    check("previous entries survive a failed rebuild", entries(risk) == ["OK"])
    boom["fail"] = False
    post(risk)
    check("recovers on the next open", entries(risk) == ["OK"])
    hm.clear_screen_items()

    root.destroy()

    print()
    if _failures:
        print(f"FAILED ({len(_failures)}): " + ", ".join(_failures))
        sys.exit(1)
    print("All dynamic-menu tests passed.")


if __name__ == "__main__":
    main()
