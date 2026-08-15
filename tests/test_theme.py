"""Tests for palette-name resolution in widget options (0.6.5).

A widget may name a palette colour where a colour is expected --- ``bg="page"``
--- and the name is swapped for the real colour before Tk builds the widget.
What was named is kept as ``widget._vcolors`` so a palette switch can
re-resolve it.  Covers what gets resolved, what is deliberately left alone,
and that nothing is touched that didn't ask.

Requires a usable Tk display; skips cleanly if Tk can't initialise.

Run: python tests/test_theme.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_failures = []


def check(label, cond):
    print(f"  {'PASS' if cond else 'FAIL'}  {label}")
    if not cond:
        _failures.append(label)


def run_resolution(root, tk, light):
    print("resolution:")
    named = tk.Label(root, text="x", bg="page", fg="muted")
    check("bg= resolves a palette name",
          str(named.cget("background")) == light.get("page"))
    check("fg= resolves a palette name",
          str(named.cget("foreground")) == light.get("muted"))
    check("the names are kept as _vcolors",
          named._vcolors.bg == "page" and named._vcolors.fg == "muted")
    check("as_dict reports every named option",
          named._vcolors.as_dict() == {"bg": "page", "fg": "muted"})

    spelled = tk.Label(root, text="x", background="page", foreground="muted")
    check("the background=/foreground= spellings resolve too",
          str(spelled.cget("background")) == light.get("page")
          and spelled._vcolors.background == "page")

    entry = tk.Entry(root, bg="card", selectbackground="accent")
    check("any colour-taking option resolves",
          str(entry.cget("selectbackground")) == light.get("accent"))

    check("chrome names are ordinary palette entries",
          str(tk.Frame(root, bg="bar_bg").cget("background")) == light.get("bar_bg"))


def run_untouched(root, tk, light):
    print("left alone:")
    literal = tk.Label(root, text="x", bg="#ff0000")
    check("a literal colour is passed straight through",
          str(literal.cget("background")) == "#ff0000")
    check("a literal colour is not tracked", not hasattr(literal, "_vcolors"))

    plain = tk.Label(root, text="x")
    check("a widget that named nothing keeps Tk's default",
          str(plain.cget("background")) != light.get("page"))
    check("a widget that named nothing is not tracked",
          not hasattr(plain, "_vcolors"))

    tkcolour = tk.Label(root, text="x", bg="red")
    check("a Tk colour name the palette doesn't define is left for Tk",
          str(tkcolour.cget("background")) == "red")

    # A '#' literal is a colour, never a name — so a palette can hold an entry
    # whose *name* looks like anything without shadowing literals.
    hexed = tk.Label(root, text="x", bg="#0a0b0c")
    check("a hex literal is never looked up",
          str(hexed.cget("background")) == "#0a0b0c"
          and not hasattr(hexed, "_vcolors"))

    words = tk.Label(root, text="page")
    check("a non-colour option is never looked up",
          words.cget("text") == "page")

    from tkinter import ttk
    ttk.Frame(root), ttk.Label(root, text="x"), ttk.Entry(root)
    check("ttk widgets construct untouched", True)


def run_switch(root, tk, light, dark):
    from VIStk.Styles import _theme

    print("palette switch:")
    named = tk.Label(root, text="x", bg="page", fg="muted")
    literal = tk.Label(root, text="x", bg="#ff0000")
    plain = tk.Label(root, text="x")
    before = str(plain.cget("background"))

    _theme.apply(dark)
    check("a named colour re-resolves", str(named.cget("background")) == dark.get("page"))
    check("both named options re-resolve",
          str(named.cget("foreground")) == dark.get("muted"))
    check("the names themselves don't change", named._vcolors.bg == "page")
    check("a literal colour is never repainted",
          str(literal.cget("background")) == "#ff0000")
    check("an unnamed widget is never repainted",
          str(plain.cget("background")) == before)

    _theme.apply(light)
    check("and back", str(named.cget("background")) == light.get("page"))

    doomed = tk.Label(root, text="x", bg="page")
    doomed.destroy()
    _theme.apply(dark)
    _theme.apply(light)
    check("a destroyed widget doesn't break a later switch", True)


def run_toggle(root, tk, light, dark):
    from VIStk.Styles import _theme

    print("exclude:")
    left_alone = tk.Label(root, text="x", bg="page")
    _theme.exclude(left_alone)
    _theme.apply(dark)
    check("an excluded widget stops following the palette",
          str(left_alone.cget("background")) == light.get("page"))
    _theme.apply(light)


def run_vwidgets(root, tk, light):
    """VIStk's own widgets must be unaffected: nothing is configured after
    construction any more, so their own colour logic runs undisturbed."""
    from VIStk.Widgets._vLabel import vLabel
    from VIStk.Widgets._vButton import vButton
    from VIStk.Widgets import TabBar

    print("VIStk widgets:")
    pane = tk.Frame(root, bg="#ffffff")
    pane.place(x=0, y=0, width=400, height=200)
    label = vLabel(pane, text="x")
    button = vButton(pane, text="x", radius=8)
    check("vLabel still inherits its parent's background",
          str(label.cget("background")) == "#ffffff")
    check("vButton keeps its radius", button._v_radius == 8)
    named = vLabel(pane, text="x", bg="page")
    check("a v-widget can name a palette colour too",
          str(named.cget("background")) == light.get("page"))

    # outline / active_fill are consumed by the widget, never reaching the
    # constructor seam — they resolve through _theme.name_to_color instead.
    from VIStk.Styles import _theme
    from VIStk.Structures._Project import Project
    rounded = vButton(pane, text="x", radius=8, bg="card",
                      outline="accent", outline_width=2, active_fill="muted")
    check("a v-widget's own colour kwargs resolve",
          rounded._v_outline == light.get("accent")
          and rounded._v_active_fill == light.get("muted"))
    check("both the base class's and the subclass's are tracked together",
          set(rounded._v_color_names) == {"_v_outline", "_v_active_fill"})
    dark = Project.getPalette("t_dark")
    _theme.apply(dark)
    check("and follow a palette switch",
          rounded._v_outline == dark.get("accent")
          and rounded._v_active_fill == dark.get("muted"))
    _theme.apply(light)

    literal = vButton(pane, text="x", radius=8, outline="#ff0000")
    _theme.apply(dark)
    check("a literal widget-held colour is never repainted",
          literal._v_outline == "#ff0000" and not literal._v_color_names)
    _theme.apply(light)

    # Route through Project so the chrome and the widget layer move together:
    # setActivePalette resolves the tab style against the palette and hands the
    # result to both.
    from VIStk.Structures._Project import Project
    Project.setActivePalette("t_light")
    bar = TabBar(root, position="top")
    bar.pack(fill="x")
    bar.open_tab(1, "One")
    root.update_idletasks()
    check("TabBar paints from the palette's chrome names",
          str(bar.cget("background")) == light.get("bar_bg"))
    bar.destroy()
    pane.destroy()


def main():
    import tkinter as tk
    try:
        root = tk.Tk()
    except tk.TclError as e:
        print(f"SKIP: no usable Tk display ({e})")
        return
    root.withdraw()

    from VIStk.Structures._Project import Project
    from VIStk.Styles import _theme

    # Two palettes sharing an open set of names, on top of the shipped roots.
    Project.registerPalette("t_light", {
        "page": "#f3f6f8", "card": "#ffffff", "muted": "#707070",
        "accent": "#1874cd", "bar_bg": "#e6e8eb",
    })
    Project.registerPalette("t_dark", {
        "page": "#242424", "card": "#333333", "muted": "#7d7d7d",
        "accent": "#1e90ff", "bar_bg": "#333333",
    }, base="dark")
    light = Project.getPalette("t_light")
    dark = Project.getPalette("t_dark")

    _theme.install()
    installed = _theme.installed()
    _theme.apply(light)

    print("install:")
    check("install() patches widget construction", installed)
    check("install() is idempotent", (_theme.install(), _theme.installed())[1])
    check("current() reports the applied palette", _theme.current() is light)

    run_resolution(root, tk, light)
    run_untouched(root, tk, light)
    run_switch(root, tk, light, dark)
    run_toggle(root, tk, light, dark)
    run_vwidgets(root, tk, light)

    _theme.uninstall()
    print("uninstall:")
    check("uninstall() restores Tk's own construction", not _theme.installed())

    root.destroy()
    print()
    if _failures:
        print(f"{len(_failures)} failed: " + ", ".join(_failures))
        sys.exit(1)
    print("all passed")


if __name__ == "__main__":
    main()
