"""Tk smoke + logic tests for the 0.6.2 v-prefixed widgets.

Exercises parent-property inheritance, explicit-option override, native
pass-through, and (PIL) rounded-corner rendering for vLabel / vButton /
vFrame.  Requires a usable Tk display (the rounded tests map a small window
to obtain real widget geometry); skips cleanly if Tk can't initialise.

Run: python tests/test_vwidgets.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_failures = []


def check(label, cond):
    print(f"  {'PASS' if cond else 'FAIL'}  {label}")
    if not cond:
        _failures.append(label)


def run_vlabel(root, tk):
    from VIStk.Widgets._vWidget import vWidget
    from VIStk.Widgets._vLabel import vLabel

    print("vLabel:")

    # Inheritance from a classic Frame parent (background only — Frames have
    # no fg/font).
    pane = tk.Frame(root, bg="#ffffff")
    pane.place(x=0, y=0, width=300, height=200)

    lbl = vLabel(pane, text="hi")
    check("is a tk.Label", isinstance(lbl, tk.Label))
    check("is a vWidget", isinstance(lbl, vWidget))
    check("inherits parent background", lbl.cget("background") == "#ffffff")

    # Explicit option wins over inheritance.
    lbl_bg = vLabel(pane, text="x", bg="#123456")
    check("explicit bg overrides inheritance", lbl_bg.cget("background") == "#123456")

    # fg / font inherit from a parent that actually carries them.
    host = tk.Label(root, bg="#eeeeee", fg="#ff0000", font="Arial 14")
    host.place(x=0, y=0, width=120, height=40)
    child = vLabel(host, text="c")
    check("inherits parent foreground", child.cget("foreground") == "#ff0000")
    check("inherits parent font", str(child.cget("font")) == "Arial 14")

    # Native pass-through still works.
    lbl.configure(text="changed")
    check("native configure(text=) works", lbl.cget("text") == "changed")

    # radius=0 → plain Label, no image painted.
    check("radius=0 sets no image", lbl.cget("image") in ("", ()))

    # radius>0 → rounded image painted once the widget has real geometry.
    pill = vLabel(pane, text="PILL", bg="#2f78d3", fg="white", radius=12)
    pill.place(x=10, y=80, width=120, height=40)
    root.update()
    check("radius>0 paints a background image", str(pill.cget("image")) != "")
    check("rounded label keeps its text", pill.cget("text") == "PILL")

    # runtime recolor repaints the rounded fill
    img_before = str(pill.cget("image"))
    pill.configure(bg="#d23f3f")
    root.update()
    check("configure(bg=) repaints the rounded fill",
          str(pill.cget("image")) != img_before)

    # a caller's bind("<Configure>") WITHOUT add="+" (e.g. fUtil.autosize) must
    # not stop the rounded render — it lives on a dedicated bindtag.
    clob = vLabel(pane, text="C", bg="#1f9d57", fg="white", radius=12)
    clob.bind("<Configure>", lambda e: None)   # clobbers the instance binding
    clob.place(x=140, y=80, width=110, height=36)
    root.update()
    check("rounded render survives a clobbering bind('<Configure>')",
          str(clob.cget("image")) != "")

    for w in (lbl, lbl_bg, child, pill, clob, pane, host):
        w.destroy()


def run_vbutton(root, tk):
    from VIStk.Widgets._vWidget import vWidget
    from VIStk.Widgets._vButton import vButton

    print("vButton:")

    pane = tk.Frame(root, bg="#ffffff")
    pane.place(x=0, y=0, width=300, height=200)

    btn = vButton(pane, text="ok")
    check("is a tk.Button", isinstance(btn, tk.Button))
    check("is a vWidget", isinstance(btn, vWidget))
    check("inherits parent background", btn.cget("background") == "#ffffff")

    # command fires through the native invoke().
    calls = []
    cbtn = vButton(pane, text="go", command=lambda: calls.append(1))
    cbtn.invoke()
    check("command fires via invoke()", calls == [1])

    check("radius=0 sets no image", btn.cget("image") in ("", ()))

    # Rounded button with a hover fill.
    chip = vButton(pane, text="Quote", bg="#eef1f6", fg="#2f78d3",
                   radius=8, active_fill="#dbe6f6")
    chip.place(x=10, y=80, width=90, height=34)
    root.update()
    img_rest = str(chip.cget("image"))
    check("radius>0 paints a background image", img_rest != "")
    check("hover binding installed", chip.bind("<Enter>") != "")

    chip.event_generate("<Enter>")
    root.update()
    check("hover repaints with active fill", str(chip.cget("image")) != img_rest)

    # disabled state: greys the fill and gates the command
    dcalls = []
    dbtn = vButton(pane, text="X", bg="#2f78d3", fg="white", radius=8,
                   disabled_fill="#eceef1", command=lambda: dcalls.append(1))
    dbtn.place(x=10, y=140, width=80, height=34)
    root.update()
    img_on = str(dbtn.cget("image"))
    dbtn.configure(state="disabled")
    root.update()
    check("disable repaints (greyed) fill", str(dbtn.cget("image")) != img_on)
    dbtn.invoke()
    check("disabled button does not fire command", dcalls == [])
    dbtn.configure(state="normal")
    dbtn.invoke()
    check("re-enabled button fires command", dcalls == [1])

    # pixel width/height honoured on a rounded widget (placeholder-image trick)
    szbtn = vButton(pane, text="Z", bg="#2f78d3", fg="white", radius=8,
                    width=90, height=40)
    szbtn.place(x=10, y=180)
    root.update()
    check("rounded button honours pixel width/height",
          abs(szbtn.winfo_width() - 90) <= 2 and abs(szbtn.winfo_height() - 40) <= 2)

    for w in (btn, cbtn, chip, dbtn, szbtn, pane):
        w.destroy()


def run_vframe(root, tk):
    from VIStk.Widgets._vWidget import vWidget
    from VIStk.Widgets._LayoutFrame import LayoutFrame
    from VIStk.Widgets._vFrame import vFrame
    from VIStk.Widgets._vLabel import vLabel

    print("vFrame:")

    pane = tk.Frame(root, bg="#dddddd")
    pane.place(x=0, y=0, width=300, height=200)

    vf = vFrame(pane)
    check("is a LayoutFrame", isinstance(vf, LayoutFrame))
    check("is a vWidget", isinstance(vf, vWidget))
    check("has a .Layout", hasattr(vf, "Layout"))
    check("inherits parent background", vf.cget("background") == "#dddddd")

    vf_bg = vFrame(pane, bg="#ffffff")
    check("explicit bg overrides inheritance", vf_bg.cget("background") == "#ffffff")
    check("plain vFrame has no rounded background", not hasattr(vf_bg, "_v_bg_label"))
    check("plain vFrame has no layout margin", vf_bg.Layout.margin == 0)

    # Rounded card with an outline: one lowered rounded image + the Layout
    # insets content off the corners (invisible when the child shares the fill).
    card = vFrame(pane, bg="#ffffff", outline="#1f9d57", radius=14)
    card.place(x=10, y=10, width=200, height=140)
    card.Layout.colSize([1.0])
    card.Layout.rowSize([1.0])
    inner = vLabel(card, text="Inside")
    inner.place(card.Layout.cell(1, 1))     # a "filling" cell — auto-inset
    root.update()
    from math import ceil
    expect_margin = ceil(14 * (1 - 2 ** -0.5))        # ceil(r·(1−1/√2))
    check("rounded vFrame builds a lowered background label",
          hasattr(card, "_v_bg_label"))
    check("background label is painted", str(card._v_bg_label.cget("image")) != "")
    check("Layout auto-margin = ceil(r*(1-1/sqrt2))",
          card.Layout.margin == expect_margin)
    check("child auto-inset off the corners by the margin",
          inner.winfo_x() == expect_margin and inner.winfo_y() == expect_margin)
    check("child inherits the card fill", inner.cget("background") == "#ffffff")

    # Regression: a pack()-ed child (no Layout.cell) must still be inset off the
    # corners — the old corner-piece overlay covered such children's text.
    badge = vFrame(pane, bg="#2f78d3", radius=16)
    badge.place(x=10, y=10, width=150, height=62)
    top = vLabel(badge, text="WORK ORDER", fg="white")
    top.pack(anchor="w")
    bottom = vLabel(badge, text="23297", fg="white")
    bottom.pack(anchor="w")
    root.update()
    root.update_idletasks()
    m = badge.Layout.margin
    check("no opaque corner-piece overlays exist", not hasattr(badge, "_v_caps"))
    check("pack()-ed children are inset off the left/top corner",
          top.winfo_x() >= m and top.winfo_y() >= m)

    for w in (vf, vf_bg, card, badge, pane):
        w.destroy()


def run_docs():
    """No Tk needed — just verifies native options were composed into the docs."""
    from VIStk.Widgets._vLabel import vLabel
    from VIStk.Widgets._vButton import vButton
    from VIStk.Widgets._vFrame import vFrame

    print("docs:")
    ldoc = vLabel.__init__.__doc__ or ""
    bdoc = vButton.__init__.__doc__ or ""
    fdoc = vFrame.__init__.__doc__ or ""

    check("vLabel doc keeps the v-widget Args (radius)", "radius:" in ldoc)
    check("vLabel doc appends native tkinter.Label options",
          "Native tkinter.Label options" in ldoc and "wraplength" in ldoc)
    check("vButton doc lists button-specific native option (command)",
          "Native tkinter.Button options" in bdoc and "command" in bdoc)
    check("vFrame doc lists frame-specific native option (colormap)",
          "Native tkinter.Frame options" in fdoc and "colormap" in fdoc)


def main():
    try:
        import tkinter as tk
    except Exception as e:
        print(f"SKIP: tkinter unavailable ({e})")
        return

    try:
        root = tk.Tk()
        root.geometry("320x240")
        root.update_idletasks()
    except Exception as e:
        print(f"SKIP: no Tk display ({e})")
        return

    try:
        run_docs()
        run_vlabel(root, tk)
        run_vbutton(root, tk)
        run_vframe(root, tk)
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
