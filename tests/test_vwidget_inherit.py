"""Tk tests for live parent-background re-inheritance (0.6.5).

A v-widget reads its inherited props off the parent at construction; this
covers the half that happens *after* construction — recolouring a parent and
having its v-children follow, through the ``Misc.configure`` seam installed by
``VIStk.Widgets._vWidget._install_bg_hook``.

The parent deliberately is *not* a v-widget in most of these: the child does
the inheriting, so a plain ``Frame`` / ``LayoutFrame`` parent must propagate
too.  Needs a usable Tk display; skips cleanly if Tk can't initialise.  The
window is created withdrawn and destroyed in a ``finally``, so the run never
leaves a window on screen or waits on one being closed.

Run: python tests/test_vwidget_inherit.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_failures = []


def check(label, cond):
    print(f"  {'PASS' if cond else 'FAIL'}  {label}")
    if not cond:
        _failures.append(label)


def run_plain_parent(root, tk):
    """A non-v parent must propagate — that is the whole point of the seam."""
    from VIStk.Widgets._vLabel import vLabel

    print("plain tk.Frame parent:")
    pane = tk.Frame(root, bg="#ffffff")
    pane.place(x=0, y=0, width=300, height=200)

    lbl = vLabel(pane, text="follows")
    fixed = vLabel(pane, text="fixed", bg="#123456")
    native = tk.Label(pane, text="native", bg="#ffffff")
    check("inherits at construction", lbl.cget("background") == "#ffffff")

    pane.configure(bg="#ff0000")
    check("follows parent recolour", lbl.cget("background") == "#ff0000")
    check("explicit bg does not follow", fixed.cget("background") == "#123456")
    check("non-v child untouched", native.cget("background") == "#ffffff")

    # The other two spellings of the same call reach the same seam.
    pane.config(background="#00ff00")
    check("config(background=) propagates", lbl.cget("background") == "#00ff00")
    pane["bg"] = "#0000ff"
    check("parent['bg'] = ... propagates", lbl.cget("background") == "#0000ff")

    # A non-colour configure must not run the walk at all.
    calls = []
    lbl._on_parent_bg = lambda: calls.append(1)
    pane.configure(width=120)
    check("non-colour configure does not notify", not calls)
    del lbl._on_parent_bg

    pane.destroy()


def run_cascade(root, tk):
    """refresh() reconfigures the child's own bg, so depth needs no recursion."""
    from VIStk.Widgets._LayoutFrame import LayoutFrame
    from VIStk.Widgets._vFrame import vFrame
    from VIStk.Widgets._vLabel import vLabel

    print("cascade through a LayoutFrame parent:")
    outer = LayoutFrame(root, bg="#ffffff")
    outer.place(x=0, y=0, width=300, height=200)
    mid = vFrame(outer)
    mid.place(x=0, y=0, width=200, height=150)
    inner = vFrame(mid)
    inner.place(x=0, y=0, width=100, height=100)
    leaf = vLabel(inner, text="deep")
    leaf.place(x=0, y=0)

    outer.configure(bg="#abcdef")
    check("depth 1 follows", mid.cget("background") == "#abcdef")
    check("depth 2 follows", inner.cget("background") == "#abcdef")
    check("depth 3 follows", leaf.cget("background") == "#abcdef")

    # An explicitly-coloured widget stops the cascade for its own subtree.
    stop = vFrame(outer, bg="#111111")
    stop.place(x=200, y=0, width=100, height=100)
    under = vLabel(stop, text="under")
    under.place(x=0, y=0)
    outer.configure(bg="#222222")
    check("explicit frame holds its colour", stop.cget("background") == "#111111")
    check("its child holds too", under.cget("background") == "#111111")

    outer.destroy()


def run_rounded(root, tk):
    """A rounded child blends its corners into the parent, explicit bg or not."""
    from VIStk.Widgets._vFrame import vFrame

    print("rounded corner blend:")
    pane = tk.Frame(root, bg="#ffffff")
    pane.place(x=0, y=0, width=300, height=200)

    card = vFrame(pane, bg="#123456", radius=10)
    card.place(x=10, y=10, width=120, height=80)
    blended = vFrame(pane, bg="#123456", radius=10, corner_bg="#00ff00")
    blended.place(x=150, y=10, width=120, height=80)
    root.update_idletasks()
    check("corner starts at parent bg", card._v_corner == "#ffffff")

    pane.configure(bg="#654321")
    check("corner follows parent", card._v_corner == "#654321")
    check("fill is untouched", card.cget("background") == "#123456")
    check("explicit corner_bg is kept", blended._v_corner == "#00ff00")

    pane.destroy()


def run_palette(root, tk):
    """A palette switch reconfigures named widgets, which feeds the same seam."""
    from VIStk.Styles import _theme
    from VIStk.Styles._palette import Palette
    from VIStk.Widgets._vLabel import vLabel

    print("palette switch:")
    _theme.apply(Palette({"surface": "#ffffff", "text": "#000000"}))
    pane = tk.Frame(root, bg="surface")
    pane.place(x=0, y=0, width=300, height=200)
    lbl = vLabel(pane, text="named")
    check("inherits the resolved colour", lbl.cget("background") == "#ffffff")

    _theme.apply(Palette({"surface": "#202020", "text": "#ffffff"}))
    check("follows the new palette", lbl.cget("background") == "#202020")

    pane.destroy()


def main():
    try:
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()
        root.geometry("320x240")
        root.update_idletasks()
    except Exception as e:
        print(f"SKIP: no Tk display ({e})")
        return

    try:
        run_plain_parent(root, tk)
        run_cascade(root, tk)
        run_rounded(root, tk)
        run_palette(root, tk)
    finally:
        try:
            root.destroy()
        except Exception:
            pass

    print()
    if _failures:
        print(f"{len(_failures)} FAILED: {_failures}")
        sys.exit(1)
    print("all passed")


if __name__ == "__main__":
    main()
