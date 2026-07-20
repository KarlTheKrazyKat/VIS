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

    # radius>0, text-only → FILL mode: the fill is painted into the image slot
    # and the text draws over it, so nothing can cover the text at any radius.
    pill = vLabel(pane, text="PILL", bg="#2f78d3", fg="white", radius=12)
    pill.place(x=10, y=80, width=120, height=40)
    root.update()
    check("text-only rounded label uses fill mode", pill._v_tile_mode is False)
    check("fill mode paints the fill into the image slot",
          str(pill.cget("image")) != "")
    check("fill mode adds no overlays (text is never covered)",
          len(pill._v_tiles) == 0 and len(pill._v_strips) == 0)
    check("rounded label keeps its text", pill.cget("text") == "PILL")

    # runtime recolor repaints the fill
    img_before = str(pill.cget("image"))
    pill.configure(bg="#d23f3f")
    root.update()
    check("configure(bg=) repaints the rounded fill",
          str(pill.cget("image")) != img_before)

    # a true circle (radius = half the short side) must still show its text —
    # this is why text-only rounding stays in fill mode.
    circ = vLabel(pane, text="7", bg="#2f78d3", fg="white", radius=30)
    circ.place(x=200, y=80, width=60, height=60)
    root.update()
    check("circle (radius = half) renders", str(circ.cget("image")) != "")
    check("circle adds no overlays (text stays visible)",
          len(circ._v_tiles) == 0 and len(circ._v_strips) == 0)

    # a caller's bind("<Configure>") WITHOUT add="+" (e.g. fUtil.autosize) must
    # not stop the rounded render — it lives on a dedicated bindtag.
    clob = vLabel(pane, text="C", bg="#1f9d57", fg="white", radius=12)
    clob.bind("<Configure>", lambda e: None)   # clobbers the instance binding
    clob.place(x=140, y=80, width=110, height=36)
    root.update()
    check("rounded render survives a clobbering bind('<Configure>')",
          str(clob.cget("image")) != "")

    # A caller image= switches to TILE mode: native image + compound (no overlap).
    from PIL import Image as _PILImage
    import PIL.ImageTk as _ImageTk
    _icon = _ImageTk.PhotoImage(_PILImage.new("RGBA", (16, 16), (255, 0, 0, 255)))
    ico = vLabel(pane, text="Item", image=_icon, compound="left", radius=12,
                 bg="#dddddd")
    ico.place(x=10, y=130, width=140, height=36)
    root.update()
    check("caller image= selects tile mode", ico._v_tile_mode is True)
    check("tile mode keeps the caller's native image=", str(ico.cget("image")) != "")
    check("tile mode keeps native compound=", str(ico.cget("compound")) == "left")
    check("tile mode builds four corner tiles", len(ico._v_tiles) == 4)

    for w in (lbl, lbl_bg, child, pill, circ, clob, ico, pane, host):
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

    from PIL import Image
    import PIL.ImageTk

    # Rounded, text-only button → fill mode (nothing overlays the label).
    chip = vButton(pane, text="Quote", bg="#eef1f6", fg="#2f78d3",
                   radius=8, active_fill="#dbe6f6")
    chip.place(x=10, y=80, width=90, height=34)
    root.update()
    check("text-only rounded button uses fill mode", chip._v_tile_mode is False)
    check("fill mode paints the fill into the image slot",
          str(chip.cget("image")) != "")
    check("fill mode adds no overlays", len(chip._v_tiles) == 0)
    check("hover binding installed", chip.bind("<Enter>") != "")

    img0 = str(chip.cget("image"))
    chip._on_enter()                     # deterministic stand-in for <Enter>
    root.update()
    check("hover recolours the button bg to active_fill",
          chip.cget("background") == "#dbe6f6")
    check("hover repaints the rounded fill", str(chip.cget("image")) != img0)

    # disabled state: greys the button and gates the command
    dcalls = []
    dbtn = vButton(pane, text="X", bg="#2f78d3", fg="white", radius=8,
                   disabled_fill="#eceef1", command=lambda: dcalls.append(1))
    dbtn.place(x=10, y=140, width=80, height=34)
    root.update()
    rest_bg = dbtn.cget("background")
    dbtn.configure(state="disabled")
    root.update()
    check("disable recolours bg to disabled_fill", dbtn.cget("background") == "#eceef1")
    dbtn.invoke()
    check("disabled button does not fire command", dcalls == [])
    dbtn.configure(state="normal")
    root.update()
    check("re-enable restores the resting bg", dbtn.cget("background") == rest_bg)
    dbtn.invoke()
    check("re-enabled button fires command", dcalls == [1])

    # radius=0: image= reaches the native widget untouched, no tiles.
    icon = PIL.ImageTk.PhotoImage(Image.new("RGBA", (16, 16), (255, 0, 255, 255)))
    flat = vButton(pane, image=icon, radius=0)
    check("radius=0 passes image= through to native", str(flat.cget("image")) != "")
    check("radius=0 builds no corner tiles", not getattr(flat, "_v_tiles", None))

    # caller image= → tile mode: NATIVE image + compound (icon beside text).
    ib = vButton(pane, text="Save", image=icon, compound="left", bg="#eef1f6",
                 radius=8, outline="#888", command=lambda: None)
    ib.place(x=120, y=140, width=120, height=36)
    root.update()
    check("caller image= selects tile mode", ib._v_tile_mode is True)
    check("tile mode keeps the caller's native image=", str(ib.cget("image")) != "")
    check("tile mode keeps native compound=", str(ib.cget("compound")) == "left")
    check("tile mode builds four corner tiles", len(ib._v_tiles) == 4)
    check("outline adds edge strips thicker than 0", len(ib._v_strips) == 4)
    check("corner tiles forward clicks to the button",
          ib._v_tiles["tl"].bind("<ButtonRelease-1>") != "")

    for w in (btn, cbtn, chip, dbtn, flat, ib, pane):
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

    # Sub-pixel corner patch: at full radius a child's corner sits a fraction of
    # a pixel over the outline; vFrame patches it with a tiny mark drawn ON the
    # child, only at the corners that child actually occupies.
    marked = vFrame(pane, bg="#e9ecef", outline="#5a6470", radius=12)
    marked.place(x=10, y=10, width=150, height=28)   # height 28 → radius stays 12
    marked.Layout.rowSize([1]); marked.Layout.colSize([0.4, 0.6])
    left = vLabel(marked, text="PM", anchor="e"); left.place(marked.Layout.cell(1, 1))
    right = vLabel(marked, text="N/A", anchor="w"); right.place(marked.Layout.cell(1, 2))
    root.update()
    marked._refresh_corner_marks()
    placed = lambda c: {k for k, mk in getattr(c, "_v_corner_marks", {}).items()
                        if mk.place_info()}
    lset, rset = placed(left), placed(right)
    check("corner patch is a child OF the content widget (drawn on the child)",
          bool(getattr(left, "_v_corner_marks", None))
          and all(mk.master is left for mk in left._v_corner_marks.values()))
    check("left child patches only its left frame corners", lset == {"tl", "bl"})
    check("right child patches only its right frame corners", rset == {"tr", "br"})
    check("corner patch is tiny (a few px — never over the text)",
          all(int(left._v_corner_marks[k].place_info()["width"]) <= 3 for k in lset))

    for w in (vf, vf_bg, card, badge, marked, pane):
        w.destroy()


def run_vimage(root, tk):
    from VIStk.Widgets._vWidget import vWidget
    from VIStk.Widgets._vImage import vImage
    import os
    import tempfile
    from PIL import Image

    print("vImage:")

    # A throwaway 80x40 PNG on disk (absolute_path avoids the Project p_images
    # lookup, so this test needs no VIStk project).
    tmp = os.path.join(tempfile.gettempdir(), "_vimage_test.png")
    Image.new("RGBA", (80, 40), (200, 30, 30, 255)).save(tmp)

    pane = tk.Frame(root, bg="#ffffff")
    pane.place(x=0, y=0, width=300, height=200)

    img = vImage(pane, tmp, absolute_path=True)
    check("is a tk.Label", isinstance(img, tk.Label))
    check("is a vWidget", isinstance(img, vWidget))
    check("inherits parent background", img.cget("background") == "#ffffff")
    check("loads via a VIMG", img.VIMG is not None)

    # Fixed-box, fit-contained: a 80x40 image in a 100x100 box -> 100x50.
    boxed = vImage(pane, tmp, absolute_path=True, size=(100, 100))
    boxed.place(x=10, y=10)
    root.update()
    check("fixed-size box paints an image", str(boxed.cget("image")) != "")
    check("contained image keeps aspect (100x50)",
          boxed._v_photo.width() == 100 and boxed._v_photo.height() == 50)

    # Rounded thumbnail.
    thumb = vImage(pane, tmp, absolute_path=True, size=(64, 64), radius=12)
    thumb.place(x=120, y=10)
    root.update()
    check("rounded image paints", str(thumb.cget("image")) != "")

    # Fit mode re-fits to the live widget size.
    fitted = vImage(pane, tmp, absolute_path=True)
    fitted.place(x=10, y=120, width=120, height=120)
    root.update()
    check("fit mode paints once laid out", str(fitted.cget("image")) != "")
    check("fit mode contains in the widget (120 wide -> 60 tall)",
          fitted._v_photo.width() == 120 and fitted._v_photo.height() == 60)

    # Swapping the source repaints.
    before = str(boxed.cget("image"))
    Image.new("RGBA", (40, 40), (30, 30, 200, 255)).save(tmp)
    boxed.set_path(tmp, absolute_path=True)
    root.update()
    check("set_path repaints", str(boxed.cget("image")) != "" and
          str(boxed.cget("image")) != before)

    # In-memory image (never on disk) via the image= constructor arg.
    mem_src = Image.new("RGBA", (120, 60), (30, 180, 90, 255))
    mem = vImage(pane, image=mem_src, size=(60, 60))
    mem.place(x=200, y=10)
    root.update()
    check("image= paints an in-memory image", str(mem.cget("image")) != "")
    check("in-memory image has no VIMG", mem.VIMG is None)
    check("in-memory image is contained (60x30)",
          mem._v_photo.width() == 60 and mem._v_photo.height() == 30)

    # set_image() swaps to another in-memory image.
    mem.set_image(Image.new("RGBA", (60, 60), (180, 30, 90, 255)))
    root.update()
    check("set_image contains a square source (60x60)",
          mem._v_photo.width() == 60 and mem._v_photo.height() == 60)

    for w in (img, boxed, thumb, fitted, mem, pane):
        w.destroy()
    try:
        os.remove(tmp)
    except OSError:
        pass


def run_vlabelframe(root, tk):
    from math import ceil
    from VIStk.Widgets._vWidget import vWidget
    from VIStk.Widgets._vLabelFrame import vLabelFrame
    from VIStk.Widgets._vLabel import vLabel

    print("vLabelFrame:")

    pane = tk.Frame(root, bg="#eef0f3")
    pane.place(x=0, y=0, width=400, height=300)

    # Plain (radius=0) → behaves like a native LabelFrame.
    lf = vLabelFrame(pane, text="Box")
    check("is a tk.LabelFrame", isinstance(lf, tk.LabelFrame))
    check("is a vWidget", isinstance(lf, vWidget))
    check("has a .Layout", hasattr(lf, "Layout"))
    check("inherits parent background", lf.cget("background") == "#eef0f3")
    check("native text passes through", lf.cget("text") == "Box")
    check("radius=0 builds no rounded bg label", not hasattr(lf, "_v_bg_label"))
    check("radius=0 has no layout margin", lf.Layout.margin == 0)
    check("radius=0 keeps no internal title", lf._v_title is None)

    # fg / font inherit from a parent that carries them (the title uses them).
    host = tk.Label(root, bg="#222222", fg="#00ff00", font="Arial 13")
    host.place(x=0, y=0, width=120, height=40)
    child = vLabelFrame(host, text="t")
    check("inherits parent foreground", child.cget("foreground") == "#00ff00")
    check("inherits parent font", str(child.cget("font")) == "Arial 13")

    # Rounded box with a title + an outline.
    box = vLabelFrame(pane, text="Title", radius=14, outline="#2f78d3",
                      outline_width=2, bg="#ffffff", fg="#1d4f7c")
    box.place(x=10, y=10, width=240, height=150)
    box.Layout.colSize([1.0]); box.Layout.rowSize([1.0])
    inner = vLabel(box, text="in", bg="#ffffff")
    inner.place(box.Layout.cell(1, 1))
    root.update(); root.update_idletasks(); root.update()
    check("rounded builds a lowered background label", hasattr(box, "_v_bg_label"))
    check("background label is painted", str(box._v_bg_label.cget("image")) != "")
    check("background label covers the WHOLE frame (not just content area)",
          box._v_bg_label.winfo_width() == box.winfo_width()
          and box._v_bg_label.winfo_height() == box.winfo_height())
    check("an internal title label is created for text mode",
          box._v_title is not None and isinstance(box._v_title, tk.Label))
    check("title is installed as the labelwidget",
          box._title_widget() is box._v_title)
    check("Layout auto-margin = ceil(r*(1-1/sqrt2))",
          box.Layout.margin == ceil(14 * (1 - 2 ** -0.5)))
    check("child inset off the corners by the margin (x)",
          inner.winfo_x() == box.Layout.margin)

    # Title options proxy to the internal title label.
    box.configure(text="New", fg="#d23f3f")
    check("configure(text=) proxies to the title (and cget reads it back)",
          box.cget("text") == "New" and box._v_title.cget("text") == "New")
    check("configure(fg=) proxies to the title",
          box._v_title.cget("fg") == "#d23f3f")
    check("item access reads the title text", box["text"] == "New")

    # Regression: pack()-ed children inset off the corners (no overlay covers them).
    badge = vLabelFrame(pane, text="WO", radius=14, outline="#16a34a", bg="#ffffff")
    badge.place(x=10, y=180, width=160, height=80)
    content = vLabel(badge, text="content", bg="#ffffff")
    content.pack(anchor="w")
    root.update(); root.update_idletasks(); root.update()
    m = badge.Layout.margin
    check("pack()-ed child inset off the corner",
          content.winfo_x() >= m and content.winfo_y() >= m)

    # A caller-supplied labelwidget is respected (no internal title made).
    lw_box = vLabelFrame(pane, radius=12, outline="#888888", bg="#ffffff")
    my_title = vLabel(lw_box, text="custom", bg="#ffffff")
    lw_box.configure(labelwidget=my_title)
    lw_box.place(x=200, y=180, width=180, height=80)
    root.update()
    check("user-supplied labelwidget made no internal title",
          lw_box._v_title is None)
    check("title widget resolves to the user's labelwidget",
          lw_box._title_widget() is my_title)

    for w in (lf, child, host, box, badge, lw_box, pane):
        w.destroy()


def run_docs():
    """No Tk needed — just verifies native options were composed into the docs."""
    from VIStk.Widgets._vLabel import vLabel
    from VIStk.Widgets._vButton import vButton
    from VIStk.Widgets._vFrame import vFrame
    from VIStk.Widgets._vLabelFrame import vLabelFrame

    print("docs:")
    ldoc = vLabel.__init__.__doc__ or ""
    bdoc = vButton.__init__.__doc__ or ""
    fdoc = vFrame.__init__.__doc__ or ""
    lfdoc = vLabelFrame.__init__.__doc__ or ""

    check("vLabel doc keeps the v-widget Args (radius)", "radius:" in ldoc)
    check("vLabel doc appends native tkinter.Label options",
          "Native tkinter.Label options" in ldoc and "wraplength" in ldoc)
    check("vButton doc lists button-specific native option (command)",
          "Native tkinter.Button options" in bdoc and "command" in bdoc)
    check("vFrame doc lists frame-specific native option (colormap)",
          "Native tkinter.Frame options" in fdoc and "colormap" in fdoc)
    check("vLabelFrame doc appends native LabelFrame options (labelanchor)",
          "Native tkinter.LabelFrame options" in lfdoc and "labelanchor" in lfdoc)


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
        run_vlabelframe(root, tk)
        run_vimage(root, tk)
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
