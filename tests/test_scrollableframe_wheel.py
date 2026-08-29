"""Tests for ScrollableFrame mouse-wheel ownership — the wheel must keep
working while the pointer is over the frame's *content*.

The wheel is routed through one class-level "who is under the pointer"
pointer, armed on ``<Enter>`` and released on ``<Leave>``.  Tk delivers a
``<Leave>`` to a widget when the pointer merely crosses into one of its
descendants, and the content frame is a child of the canvas — so releasing on
every ``<Leave>`` dropped the wheel the instant the pointer touched anything
the frame contained.  ``_on_leave`` now asks what is actually under the
pointer before letting go.

These windows must stay mapped: ``winfo_containing`` reports nothing for a
withdrawn one.  They are small, live for well under a second, and are torn
down in a ``finally`` — closing one by hand mid-run is what raises TclError,
so the run does not depend on the window surviving.

Run: python tests/test_scrollableframe_wheel.py
"""
import os
import sys
import time
from tkinter import Tk, Label, Canvas

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from VIStk.Widgets._ScrollableFrame import ScrollableFrame  # noqa: E402

_failures = []


def check(label, cond):
    print(f"  {'PASS' if cond else 'FAIL'}  {label}")
    if not cond:
        _failures.append(label)


def new_root():
    root = Tk()
    root.geometry("500x300+60+60")
    # A hand-close mid-run would leave the rest of the script driving a dead
    # interpreter; ignore it and let the finally-block do the teardown.
    root.protocol("WM_DELETE_WINDOW", lambda: None)
    return root


def teardown(root, *frames):
    """Drop pending after() jobs before destroy so nothing fires on a dead Tk."""
    for f in frames:
        for job in (f._scroll_anim, f._scrollregion_job):
            if job is not None:
                try:
                    f.after_cancel(job)
                except Exception:
                    pass
    root.destroy()


def center(w):
    return (w.winfo_rootx() + w.winfo_width() // 2,
            w.winfo_rooty() + w.winfo_height() // 2)


def leave(widget, root, x, y):
    """Synthesise the <Leave> Tk sends when the pointer moves to (x, y)."""
    widget.event_generate("<Leave>", rootx=x, rooty=y)
    root.update()


def settle(root, frame, timeout=2.0):
    """Run the event loop until the smooth-scroll animation finishes."""
    deadline = time.monotonic() + timeout
    while frame._scroll_anim is not None and time.monotonic() < deadline:
        root.update()
        time.sleep(0.005)


def test_single_frame():
    print("single frame")
    root = new_root()
    sf = ScrollableFrame(root)
    sf.pack(fill="both", expand=True)
    rows = [Label(sf.scrollable_frame, text=f"row {i}") for i in range(60)]
    for r in rows:
        r.pack(fill="x")
    root.update_idletasks()
    root.update()
    try:
        sf.canvas.event_generate("<Enter>", x=5, y=5)
        root.update()
        check("bare canvas claims the wheel", ScrollableFrame._active is sf)

        # The regression: pointer crosses off the canvas onto its own content.
        leave(sf.canvas, root, *center(rows[3]))
        check("pointer over content keeps the wheel", ScrollableFrame._active is sf)

        before = sf.canvas.canvasy(0)
        sf.canvas.event_generate("<MouseWheel>", delta=-120)
        root.update()
        settle(root, sf)
        check("wheel scrolls while over content", sf.canvas.canvasy(0) > before)

        leave(sf.canvas, root, -500, -500)
        check("leaving the frame releases the wheel", ScrollableFrame._active is None)
    finally:
        teardown(root, sf)


def test_nested_frames():
    print("nested frames")
    root = new_root()
    outer = ScrollableFrame(root)
    outer.pack(fill="both", expand=True)
    top = Label(outer.scrollable_frame, text="outer row", height=2)
    top.pack(fill="x")
    # Fixed size, no fill/expand: an inner frame that grows to fit its parent,
    # inside an outer one that grows to fit its content, never settles.
    inner = ScrollableFrame(outer.scrollable_frame, width=400, height=150)
    inner.pack_propagate(False)
    inner.pack()
    irows = [Label(inner.scrollable_frame, text=f"inner {i}") for i in range(30)]
    for r in irows:
        r.pack(fill="x")
    root.update_idletasks()
    root.update()
    try:
        outer.canvas.event_generate("<Enter>", x=5, y=5)
        root.update()
        check("outer claims the wheel", ScrollableFrame._active is outer)

        # Tk sends the ancestor's <Leave> before the inner frame's <Enter>.
        inner_pt = center(irows[2])
        leave(outer.canvas, root, *inner_pt)
        check("outer holds it mid-crossing", ScrollableFrame._active is outer)
        inner.canvas.event_generate("<Enter>", x=5, y=5)
        root.update()
        check("innermost frame under the pointer wins", ScrollableFrame._active is inner)

        leave(inner.canvas, root, *center(top))
        check("inner releases on a real exit", ScrollableFrame._active is None)
        outer.canvas.event_generate("<Enter>", x=5, y=5)
        root.update()
        check("outer re-arms", ScrollableFrame._active is outer)

        # Only the current owner may release: order of delivery cannot matter.
        leave(inner.canvas, root, -500, -500)
        check("a non-owner's <Leave> is ignored", ScrollableFrame._active is outer)
        inner.canvas.event_generate("<Enter>", x=5, y=5)
        root.update()
        leave(outer.canvas, root, *inner_pt)
        check("a stale ancestor <Leave> cannot steal from inner",
              ScrollableFrame._active is inner)
    finally:
        teardown(root, outer, inner)


def test_survives_foreign_unbind_all():
    """A third party's unbind_all must not cost us the wheel for good.

    ``bind_all``/``unbind_all`` is a common Tk idiom for "scroll this canvas
    while the pointer is over it", and ``unbind_all`` drops every handler for
    the sequence, ours included — app-wide, and permanently, since ``_bound``
    stays True so construction never re-binds.  ``_on_enter`` re-asserts it.
    """
    print("foreign unbind_all")
    root = new_root()
    sf = ScrollableFrame(root)
    sf.pack(fill="both", expand=True)
    for i in range(60):
        Label(sf.scrollable_frame, text=f"row {i}").pack(fill="x")
    root.update_idletasks()
    root.update()
    try:
        # Not asserted at construction: `_bound` is class-level for the whole
        # process, so a second Tk root (this file's third test) is skipped by
        # `_bind_scroll_global` entirely. Entering the frame is what guarantees
        # the binding now — which is the same mechanism under test below.
        sf.canvas.event_generate("<Enter>", x=5, y=5)
        root.update()
        check("entering a frame installs the binding", bool(root.bind_all("<MouseWheel>")))

        Canvas(root).unbind_all("<MouseWheel>")
        check("a foreign unbind_all removes it", not bool(root.bind_all("<MouseWheel>")))
        check("_bound stays True, so construction will not re-bind",
              ScrollableFrame._bound)

        sf.canvas.event_generate("<Enter>", x=5, y=5)
        root.update()
        check("entering it again re-asserts the binding", bool(root.bind_all("<MouseWheel>")))

        before = sf.canvas.canvasy(0)
        sf.canvas.event_generate("<MouseWheel>", delta=-120)
        root.update()
        settle(root, sf)
        check("and the wheel scrolls again", sf.canvas.canvasy(0) > before)
    finally:
        teardown(root, sf)


if __name__ == "__main__":
    test_single_frame()
    test_nested_frames()
    test_survives_foreign_unbind_all()
    print("ALL PASS" if not _failures else f"FAILED: {_failures}")
    sys.exit(1 if _failures else 0)
