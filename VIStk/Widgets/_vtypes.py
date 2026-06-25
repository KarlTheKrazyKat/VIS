"""Typed option maps for the v-widgets (0.6.2).

These ``TypedDict``s re-declare the native tkinter options each classic widget
accepts — the ones tkinter itself hides behind ``**kw`` — so editors (Pylance,
PyCharm) surface them as keyword completions on ``vLabel`` / ``vButton`` /
``vFrame`` alongside each widget's own ``radius`` / ``outline`` params.

They are referenced only through ``**kwargs: Unpack[...]`` annotations guarded by
``TYPE_CHECKING`` in the widget modules, so they cost nothing at runtime.  The
option sets mirror ``<widget>.keys()`` for the installed Tk (including the
``bg`` / ``fg`` / ``bd`` aliases) and are extremely stable across versions.
``help(vLabel)`` shows the live, authoritative list pulled straight from
tkinter's own docstring (see :class:`~VIStk.Widgets._vWidget.vWidget`), so this
file is the editor-time mirror of that runtime behaviour.
"""

from __future__ import annotations

from typing import Any, Callable, TypedDict
from tkinter import Variable


class _CommonKw(TypedDict, total=False):
    """Options accepted by Label, Button and Frame alike."""
    background: str
    bg: str
    borderwidth: str | int
    bd: str | int
    cursor: str
    height: str | int
    highlightbackground: str
    highlightcolor: str
    highlightthickness: str | int
    padx: str | int
    pady: str | int
    relief: str
    takefocus: Any
    width: str | int


class _TextKw(_CommonKw, total=False):
    """Text/appearance options shared by Label and Button."""
    activebackground: str
    activeforeground: str
    anchor: str
    bitmap: str
    compound: str
    disabledforeground: str
    fg: str
    font: Any
    foreground: str
    image: Any
    justify: str
    state: str
    text: Any
    textvariable: Variable
    underline: int
    wraplength: str | int


class _LabelKw(_TextKw, total=False):
    """Native :class:`tkinter.Label` options."""


class _ButtonKw(_TextKw, total=False):
    """Native :class:`tkinter.Button` options."""
    command: Callable[[], Any]
    default: str
    overrelief: str
    repeatdelay: int
    repeatinterval: int


class _FrameKw(_CommonKw, total=False):
    """Native :class:`tkinter.Frame` options."""
    class_: str
    colormap: Any
    container: bool
    visual: Any
