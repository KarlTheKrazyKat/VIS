Widgets
=======

Widgets extend Tkinter with compound components. Import from ``VIStk.Widgets``.

.. contents:: On this page
   :local:
   :depth: 2

----

TabBar
------

``TabBar(Frame)`` — A row of clickable tabs displayed at the top of a ``TabManager``. Each tab
has a label button and a close button (✕). A thin vertical separator divides adjacent tabs. Tabs
can be reordered by dragging, detached into their own window, or merged into another ``TabBar``.

``TabBar`` is created automatically by ``TabManager.__init__`` and exposed as
``host.TabManager.tab_bar``. You do not normally need to interact with it directly.

Interaction model
~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Action
     - Behaviour
   * - Click
     - Focuses the tab.
   * - Close button (✕)
     - Closes the tab.
   * - Right-click
     - Context menu with **Open in new window**, **Force refresh**, and **Close**.
   * - Drag (≥ 8 px)
     - Shows a semi-transparent ghost window following the cursor; a thin blue insertion
       indicator appears in the hovered bar showing where the tab will land.
   * - Release over the same bar
     - Reorders the tab to the indicated position.
   * - Release over another bar
     - Merges the tab into that bar.
   * - Release outside all bars
     - Detaches the tab into a new ``DetachedWindow``.

Attributes
~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 30 20 50

   * - Attribute
     - Type
     - Description
   * - ``tabbar.active``
     - ``str / None``
     - Name of the currently focused tab.
   * - ``tabbar.owner``
     - ``TabManager / None``
     - The ``TabManager`` that owns this bar.
   * - ``tabbar.on_focus_change``
     - ``callable / None``
     - ``(name: str / None)`` — called when the active tab changes.
   * - ``tabbar.on_tab_close``
     - ``callable / None``
     - ``(name: str)`` — called when the close button is pressed.
   * - ``tabbar.on_tab_popout``
     - ``callable / None``
     - ``(name: str)`` — called when "Open in new window" is chosen.
   * - ``tabbar.on_tab_refresh``
     - ``callable / None``
     - ``(name: str)`` — called when "Force refresh" is chosen.
   * - ``tabbar.on_drag_detach``
     - ``callable / None``
     - ``(name: str)`` — called when a drag is released outside all bars.
   * - ``tabbar.on_drag_merge``
     - ``callable / None``
     - ``(name: str, source: TabBar, idx: int)`` — called when a drag from ``source`` is
       released over this bar.

Methods
~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 40 15 45

   * - Method
     - Returns
     - Description
   * - ``open_tab(name, icon=None, insert_idx=-1)``
     - ``bool``
     - Add a tab. Does nothing if already open. Returns ``True`` if a new tab was created,
       ``False`` if it already existed.
   * - ``close_tab(name)``
     - ``bool``
     - Remove the tab. Returns ``True`` if removed, ``False`` if not found.
   * - ``focus_tab(name)``
     - ``bool``
     - Set ``name`` as active. Returns ``True`` on success.
   * - ``has_tab(name)``
     - ``bool``
     - Return whether a tab with ``name`` is open.
   * - ``get_tab_idx(name)``
     - ``int``
     - Return the 0-based position, or ``-1`` if not present.
   * - ``set_insert_indicator(idx)``
     - —
     - Show the blue insertion indicator at position ``idx``.
   * - ``clear_insert_indicator()``
     - —
     - Hide the insertion indicator.
   * - ``destroy()``
     - —
     - Deregisters from ``_TABBAR_REGISTRY`` then destroys the widget.

Styling (0.6.2)
~~~~~~~~~~~~~~~

The tab bar's colours and shape come from a named **style** (see
``VIStk.Styles``), which the end user picks in **Settings > Appearance > Tab
style**. Four looks ship: ``classic`` (the historical grey bar), ``underline``
(flat tabs, accent bar under the active one), ``topline`` (fill cue + accent
bar on top), and ``pill`` (a rounded accent capsule). Styling is process-wide
class state --- the methods below are classmethods that apply live to every
open bar and become the style for new ones. Configure them once at startup from
``Screens/styles.py`` (imported by the Host before the first window opens), or
call them at runtime.

.. list-table::
   :header-rows: 1
   :widths: 45 55

   * - Method
     - Description
   * - ``TabBar.setStyle(name)``
     - Switch to a built-in style by name (``"classic"``, ``"underline"``,
       ``"topline"``, ``"pill"``). Raises ``ValueError`` for an unknown name.
   * - ``TabBar.setPalette(*, bar=, tab=, selected=, text=, close=, selected_text=)``
     - Recolour the active style. Each argument is a Tk colour (``"grey62"``
       or ``"#1e90ff"``); omitted ones are unchanged. Overrides are
       **sticky** --- re-applied on top of every style, so they survive a
       ``setStyle`` switch and the user's saved pick at launch.
   * - ``TabBar.offer_styles(names, default=None)``
     - Curate which style names the Settings dropdown offers, and set the
       fallback default.
   * - ``TabBar.register_tab_style(name, style)``
     - Register a custom ``TabStyle`` (usually built with
       ``TabStyle.from_preset(...)``) so it can be offered.

``setPalette`` colour roles: ``bar`` (the tab-strip background), ``tab`` (an
unselected tab), ``selected`` (the selected tab), ``text`` (label + ✕ colour on
every tab), ``close`` (the ✕ close-button highlight), ``selected_text``
(label + ✕ on the selected tab only).

.. code-block:: python

    # Screens/styles.py — runs once at startup, before the first window opens
    from VIStk.Widgets import TabBar

    TabBar.setStyle("pill")
    TabBar.setPalette(bar="#dddddd", tab="#f6f6f6", selected="#5d9edc",
                      text="#0000cd", close="#cd0000")

Registry
~~~~~~~~

All live ``TabBar`` instances are tracked in ``VIStk.Widgets._TabBar._TABBAR_REGISTRY``. This
list is used during drag motion to detect cross-bar merges.

----

SplitView
---------

``SplitView(Frame)`` — A tree-of-panes container that allows the Host (or DetachedWindow) content
area to be divided into multiple panes, each with its own ``TabManager`` and ``TabBar``. Panes are
separated by draggable sashes.

Each ``SplitView`` instance holds a root widget that is either a single ``TabManager`` (no split)
or a ``_SplitNode`` wrapping a ``ttk.PanedWindow`` with two child slots. Each slot is either a
``TabManager`` (leaf) or another ``_SplitNode`` (branch), forming an arbitrary binary tree.

Import: ``from VIStk.Widgets._SplitView import SplitView``

Key methods
~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Method
     - Description
   * - ``split(pane, direction, exclude=None)``
     - Split *pane* into two side-by-side panes. *direction* is ``"right"`` (horizontal) or
       ``"down"`` (vertical). Returns ``(left_pane, right_pane)``. Tabs in *pane* transfer to
       *left_pane*; names in *exclude* are skipped.
   * - ``remove_pane(pane)``
     - Collapse *pane* out of the tree, promoting the surviving sibling. If the root becomes a
       single ``TabManager``, the ``_SplitNode`` wrapper is dissolved.
   * - ``all_tab_managers()``
     - Walk the tree and return all leaf ``TabManager`` instances.
   * - ``all_tabs()``
     - Aggregate ``_tabs`` dicts from all panes into a single dict.
   * - ``find_pane_for_tab(name)``
     - Locate which ``TabManager`` owns *name*; returns ``None`` if not found.
   * - ``set_callbacks(callbacks)``
     - Store a callback dict and apply to all current and future ``TabManager`` panes.

Focus tracking
~~~~~~~~~~~~~~

- ``focused_pane`` (property) — the ``TabManager`` the user last interacted with.
- Clicking anywhere inside a pane (including child widgets like buttons) sets that pane as focused
  via a toplevel-level ``<Button-1>`` binding.
- ``_global_focused_pane`` (class attribute) — tracks the last-focused pane across all windows
  (Host and DetachedWindows). Used by ``Host._open_tab()`` to open new tabs in the correct pane.
- When a window loses OS focus, all pane focus indicators dim. They restore on ``<FocusIn>``.

Drag-to-split
~~~~~~~~~~~~~

- Dragging a tab into the outer 25% of any pane's content area shows a translucent blue overlay
  (``Toplevel`` with ``alpha=0.22``) indicating the split direction.
- Dragging to the center shows a full-pane overlay; dropping there adds the tab to that pane.
- ``detect_drop_zone(x_root, y_root)`` — returns ``(pane, direction)`` or ``None``.
- ``detect_any_drop_zone(x_root, y_root)`` — class method that checks all registered SplitViews,
  respecting window z-order via ``wm stackorder``.
- ``lift_window_at(x_root, y_root)`` — class method that lifts the target window to the front
  when the cursor enters its non-overlapping area during a drag.

Cross-window support
~~~~~~~~~~~~~~~~~~~~

All live ``SplitView`` instances are tracked in ``SplitView._registry`` (class-level list).
This enables cross-window drag-to-split: a tab dragged from one window can be dropped into a
split zone in another window.

When windows overlap, only the frontmost window at the cursor position shows drop zones.
The stacking order is determined by Tk's ``wm stackorder`` command.

----

HostMenu
--------

``HostMenu`` wraps a ``tk.Menu`` attached to the Host window. It has three ordered layers:

1. **Built-in layer** — the ``App`` cascade (Close Window / Quit), always first, built
   automatically by ``attach()``.
2. **Project layer** — app-wide cascades defined once in ``Host.py`` at startup via
   ``set_project_items()``; persist across all tab changes.
3. **Screen layer** — cascades contributed by the active tab's ``configure_menu()`` hook via
   ``set_screen_items()``; all cleared automatically on tab deactivation.

``HostMenu`` is created automatically by ``Host.__init__`` and exposed as ``host.HostMenu``.

Item spec format
~~~~~~~~~~~~~~~~

.. code-block:: python

    # Simple command
    {"label": "Open",  "command": open_fn}

    # Cascade submenu
    {"label": "Export", "items": [
        {"label": "PDF",  "command": export_pdf},
        {"label": "CSV",  "command": export_csv},
    ]}

    # Separator
    {"separator": True}

Methods
~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 45 55

   * - Method
     - Description
   * - ``attach()``
     - Configure the parent window to show this menu bar and build the base items.
       Called once by ``Host``.
   * - ``set_project_items(items, label="Project")``
     - Add one cascade to the project layer. May be called multiple times. Persists
       across all tab changes.
   * - ``add_project_command(label, command, image=None, compound=None, align=None)``
     - Add one *leaf* command directly to the menu bar (project layer) — a top-level
       entry whose label **is** the action, e.g. ``Help``. ``image`` accepts a Tk
       ``PhotoImage`` or a ``PIL.Image.Image``; a PIL image is rendered natively on the
       Windows menu bar strip (see below). ``align="right"`` right-justifies the entry
       natively; ignored off-Windows. May be called multiple times.
   * - ``clear_project_items()``
     - Remove all project-layer cascades. Intended for teardown.
   * - ``set_screen_items(items, label="Screen")``
     - Accumulates — adds one cascade to the screen layer. Call multiple times in one
       ``configure_menu`` hook to contribute multiple cascades. All cleared together on
       tab deactivation.
   * - ``clear_screen_items()``
     - Remove all accumulated screen cascades. Called automatically on tab deactivation.
   * - ``set_native_image(label, pil_image)``
     - Swap the native bitmap on an existing entry **in place**. The Tk entry is not
       touched, so Tk does not rebuild the native menu (an ``entryconfigure`` would drop
       every native patch and flicker). Frees the replaced ``HBITMAP``. Returns ``False``
       off-Windows, for an unknown *label*, or on any native failure.
   * - ``refresh_native()``
     - Re-apply every registered native patch by each label's *current* index; labels
       that no longer resolve are skipped. Runs automatically (coalesced) after every
       menu-bar-mutating method — public only as an escape hatch for callers that mutate
       ``menubar`` directly.
   * - ``native_menubar_supported()`` *(static)*
     - ``True`` when native menu bar patching (bitmaps / right-align) is available —
       i.e. on Windows.
   * - ``native_menu_height()`` *(static)*
     - Native menu bar height in pixels (``SM_CYMENU``); falls back to ``20`` elsewhere.
       Use it to size a bitmap to the bar.

``build_shared_menu`` / ``apply_overrides`` / ``reset_overrides`` / ``save_defaults`` /
``restore_defaults`` / ``detach`` also exist but are framework lifecycle plumbing driven
by ``Host`` and ``DetachedWindow`` — application and screen code should not call them.

Native menu bar images & right-alignment (Windows, 0.6.1)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Tk accepts ``image=`` on a menu bar entry, but the native Windows menu never renders it,
and Tk exposes no right-justify at all. When ``add_project_command`` is given a **PIL**
image (and/or ``align="right"``), ``HostMenu`` patches the real ``HMENU`` *after* Tk has
built it — ``VIStk/Widgets/_MenuNative.py`` renders premultiplied-alpha DIB bitmaps and
sets ``MFT_RIGHTJUSTIFY`` through ``SetMenuItemInfoW``.

Tk rebuilds the native menu on **every** Tk-side mutation and drops those out-of-band
patches, so ``HostMenu`` re-applies them automatically — coalesced on ``after_idle`` —
after each mutating method and on ``<Map>`` (a remap recreates the wrapper window, so the
old ``HMENU`` handle is gone).

.. code-block:: python

    from PIL import Image

    host.HostMenu.add_project_command(
        "Status",
        command=show_status,
        image=Image.open(badge_path),
        align="right",
    )

    # Later: swap the bitmap without a Tk-side rebuild
    host.HostMenu.set_native_image("Status", Image.open(alert_path))

.. note::

   Win32 quirk: a right-justified entry drags **every entry after it** to the right, so
   ``HostMenu`` inserts new left-side entries *before* the right-aligned block rather
   than appending them.

Off-Windows a PIL image degrades to an ``ImageTk.PhotoImage`` (which Tk-drawn menu bars,
e.g. on X11, do render) and ``align`` is ignored. For a *live widget* pinned at the menu
bar's right edge — rather than a static bitmap — use ``host.register_menubar_accessory``
instead.

Attributes
~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 25 15 60

   * - Attribute
     - Type
     - Description
   * - ``hostmenu.menubar``
     - ``Menu``
     - The underlying ``tk.Menu`` widget.

Usage pattern
~~~~~~~~~~~~~

Project-wide items are set once in ``Host.py``:

.. code-block:: python

    host = Host()
    host.HostMenu.set_project_items([
        {"label": "File", "items": [
            {"label": "New",  "command": new_fn},
            {"separator": True},
            {"label": "Exit", "command": host.quit_host},
        ]},
    ], label="File")

Screen-specific items are contributed via ``configure_menu``. A screen that needs multiple
cascades calls ``set_screen_items`` more than once — all are cleared together when the tab
loses focus:

.. code-block:: python

    def configure_menu(menubar):
        menubar.set_screen_items([
            {"label": "Export PDF", "command": export_pdf},
            {"label": "Print",      "command": print_fn},
        ], label="Work Orders")

        menubar.set_screen_items([
            {"label": "About", "command": show_about},
        ], label="Help")

----

InfoRow
-------

``InfoRow(Frame)`` — A slim status bar packed at the bottom of the Host window. Created
automatically by ``Host.__init__`` and exposed as ``host.InfoRow``.

.. list-table::
   :header-rows: 1
   :widths: 15 85

   * - Zone
     - Content
   * - Left
     - Active screen name and version, updated on tab focus change.
   * - Centre
     - Project copyright string (static, set at startup).
   * - Right
     - App version and live FPS counter, e.g. ``v1.0.0  |  30.0 fps``.

The copyright string is normalised at construction: if it does not already contain ``©``, the
current year and ``©`` are automatically prepended.

Methods
~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 35 65

   * - Method
     - Description
   * - ``set_screen(name, version="")``
     - Update the screen label. Pass empty strings to clear.
   * - ``set_fps(fps)``
     - Update the FPS counter. Called by ``Host.tick_fps()``.

``InfoRow`` is managed entirely by ``Host`` — you do not need to call its methods directly.

----

ScrollableFrame
---------------

``ScrollableFrame(ttk.Frame)`` — A frame with a vertical scrollbar. Content is placed inside
``scrollable_frame``. Mouse wheel scrolling activates when the cursor enters the frame and
deactivates when it leaves.

.. code-block:: python

    from VIStk.Widgets import ScrollableFrame

    sf = ScrollableFrame(parent)
    sf.pack(fill=BOTH, expand=True)

    # Place content inside scrollable_frame, not sf directly
    Label(sf.scrollable_frame, text="Item 1").pack()
    Label(sf.scrollable_frame, text="Item 2").pack()

Attributes
~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 28 18 54

   * - Attribute
     - Type
     - Description
   * - ``sf.canvas``
     - ``Canvas``
     - The underlying canvas that enables scrolling.
   * - ``sf.scrollbar``
     - ``ttk.Scrollbar``
     - The vertical scrollbar.
   * - ``sf.scrollable_frame``
     - ``Frame``
     - The inner frame — place all content here.

.. note::

   All child widgets must be placed inside ``sf.scrollable_frame``, not inside ``sf`` itself.

----

VISMenu
-------

``VISMenu`` builds a column of buttons from a JSON file. Each button can launch a screen by
name or a script/executable by path. Keyboard shortcuts are supported via a ``nav`` character
per item.

JSON format
~~~~~~~~~~~

.. code-block:: text

    {
        "Work Orders": {
            "text": "Work Orders",
            "path": "wo",
            "nav": "w"
        },
        "Rolodex": {
            "text": "Rolodex",
            "path": "rolo",
            "nav": "r"
        }
    }

.. list-table::
   :header-rows: 1
   :widths: 15 85

   * - Key
     - Description
   * - ``text``
     - Button label.
   * - ``path``
     - Screen name, path to a ``.py`` script, or path to an ``.exe``.
   * - ``nav``
     - Single character — pressing this key activates the button.

Usage
~~~~~

.. code-block:: python

    from VIStk.Widgets import VISMenu

    from Screens.Landing.j_administrate import menu as admin_data

    menu = VISMenu(parent_frame, admin_data)

----

MenuItem
--------

``MenuItem(Button)`` — A single button used by ``VISMenu``. Can be created directly for
individual menu-style buttons without a ``j_``-driven menu.

.. code-block:: python

    from VIStk.Widgets import MenuItem

    btn = MenuItem(parent, path="wo", nav="w", text="Work Orders", relief="flat")
    btn.grid(row=0, column=0, sticky=(N,S,E,W))

The button highlights blue on hover and returns to default on leave. Clicking calls
``itemPath()``, which loads the screen or opens the path.

----

MenuWindow
----------

``MenuWindow(SubRoot)`` — A floating popup window containing a ``VISMenu``. Automatically
centers itself over the parent window.

.. code-block:: python

    from VIStk.Widgets import MenuWindow

    from Screens.Landing.j_administrate import menu as admin_data

    menu_win = MenuWindow(root, admin_data)

----

ScrollMenu
----------

``ScrollMenu(ScrollableFrame)`` — A scrollable ``VISMenu``. Useful when the menu has more
items than can fit on screen.

.. code-block:: python

    from VIStk.Widgets import ScrollMenu
    from Screens.Landing.j_administrate import menu as admin_data

    sm = ScrollMenu(parent, admin_data)
    sm.pack(fill=BOTH, expand=True)

The ``VISMenu`` is placed inside the ``scrollable_frame``. Access the underlying menu via
``sm.VISMenu``.

----

QuestionWindow
--------------

``QuestionWindow(SubRoot)`` — A configurable dialog window with a question and one or more
response buttons. Centers on the parent window.

.. code-block:: python

    from VIStk.Widgets import QuestionWindow

    dlg = QuestionWindow(
        question="Save changes before closing?",
        answer="yn",
        parent=root,
        ycommand=save_and_close
    )

Constructor
~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 15 20 65

   * - Parameter
     - Type
     - Description
   * - ``question``
     - ``str`` or ``list[str]``
     - Text to display. A list creates one label per item.
   * - ``answer``
     - ``str``
     - A string of character codes defining the buttons (see below).
   * - ``parent``
     - ``Tk / Toplevel``
     - The window to center on.
   * - ``ycommand``
     - ``callable``
     - Function called when an affirmative button is clicked. The window is destroyed first.
   * - ``droplist``
     - ``list``
     - Values for a dropdown (``"d"``) button.

Answer codes
~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 10 20 70

   * - Code
     - Button Text
     - Action
   * - ``y``
     - Yes
     - Destroys window, calls ``ycommand``.
   * - ``n``
     - No
     - Destroys window.
   * - ``r``
     - Return
     - Destroys window.
   * - ``u``
     - Continue
     - Destroys window, calls ``ycommand``.
   * - ``b``
     - Back
     - Destroys window.
   * - ``x``
     - Close
     - Destroys window.
   * - ``c``
     - Confirm
     - Destroys window, calls ``ycommand``.
   * - ``d``
     - *(dropdown)*
     - ``ttk.Combobox`` populated from ``droplist``.

Examples
~~~~~~~~

.. code-block:: python

    # Yes / No
    QuestionWindow("Delete this record?", "yn", root, ycommand=delete_record)

    # Confirm / Back
    QuestionWindow(["Are you sure?", "This cannot be undone."], "cb", root, ycommand=proceed)

    # Multi-line with dropdown
    QuestionWindow("Select output format:", "dx", root, droplist=["PDF", "CSV", "JSON"])

----

WarningWindow
-------------

``WarningWindow(QuestionWindow)`` — A modal warning dialog with a single "Continue" button.

.. code-block:: python

    from VIStk.Widgets import WarningWindow

    WarningWindow("File not found.", parent=root)

The window is automatically made modal (``modalize()``), blocking input to the parent until
dismissed. Use for non-recoverable error messages where the user must acknowledge before
continuing.


----

Tooltip (0.5.0)
---------------

Hover tooltip bound to any widget. Tkinter has no native tooltip.

.. code-block:: python

    from VIStk.Widgets import Tooltip
    Tooltip(my_button, text="Save the current document")

``text`` may be a string or a zero-arg callable for state-dependent
tooltips (re-evaluated each show). Cleans up its ``after`` callback on
widget destroy.

Keyword args: ``delay_ms=500``, ``wraplength=240``, ``background``,
``foreground``, ``borderwidth``.

----

CollapsibleFrame (0.5.0)
------------------------

Frame whose body is hidden under a header button. Pack children into
``cf.body`` (NOT directly into the frame).

.. code-block:: python

    from VIStk.Widgets import CollapsibleFrame
    cf = CollapsibleFrame(parent, text="Advanced", expanded=False)
    cf.pack(fill="x")
    ttk.Entry(cf.body).pack()

``cf.expanded_var`` is a ``BooleanVar`` callers can bind to share state
or persist it. Methods: ``expand()``, ``collapse()``, ``toggle()``,
``set_expanded(bool)``, ``set_text(str)``.

----

AutocompleteEntry (0.5.0)
-------------------------

``ttk.Entry`` with a filtered dropdown ``Listbox`` of suggestions.

.. code-block:: python

    from VIStk.Widgets import AutocompleteEntry
    AutocompleteEntry(parent, values=["Boston", "Chicago", ...]).pack()

``values`` may be an iterable or a callable ``(text) -> iterable``
(use the callable form for dynamic lookups).

Keyword args: ``max_results=8``, ``case_sensitive=False``,
``match="prefix"`` (or ``"contains"``).

Keyboard: ``Up``/``Down`` move, ``Return`` accepts, ``Tab`` accepts the
first match, ``Escape`` closes the popup.

----

DateEntry (0.5.0)
-----------------

Date input with format validation and a calendar-picker popup. No
third-party dependencies.

.. code-block:: python

    from VIStk.Widgets import DateEntry
    de = DateEntry(parent, date_format="%Y-%m-%d")
    de.pack()

``de.get()`` returns ``date | None``. ``de.set(d)`` sets
programmatically. Invalid manual input reverts to the last valid value
on focus-out. Keyword args include ``initial: date | None``,
``on_change: callable``, ``entry_width: int``.

Since 0.6.2 the calendar popup flips to open *above* the entry when
opening below would spill past the bottom of the containing window (or
screen) --- e.g. a date field near the bottom of a form --- falling back
to below when there is no room above either.

----

confirm / confirm_discard (0.5.0)
---------------------------------

Drop-in modal helpers so screens stop reimplementing
:mod:`tkinter.messagebox`.

.. code-block:: python

    from VIStk.Widgets import confirm, confirm_discard

    if confirm(parent, title="Delete?", message="Really delete?"):
        ...

    choice = confirm_discard(parent, name="Work Order #12345")
    if choice == "cancel":
        return False                # veto on_quit
    if choice == "save":
        _save()
    return True

Both dialogs centre on the parent via ``WindowGeometry.center_on``
(no flicker), are modal/transient, and return plain values
(``bool`` for ``confirm``; ``"save" | "discard" | "cancel"`` for
``confirm_discard``). Closing the window or pressing Escape returns
the negative outcome.

----

ContextMenu (0.5.4)
-------------------

Right-click popup menu wrapping :class:`tkinter.Menu` + ``tk_popup`` so
screens stop re-rolling the bind/build/popup boilerplate. This is the
*native* menu — keyboard navigation, hover submenus, click-outside
dismissal and screen-edge clipping all come for free. It renders as the
classic system menu, not a ttk-themed widget.

.. code-block:: python

    from VIStk.Widgets import ContextMenu

    ContextMenu(my_tree, items=[
        {"label": "Insert step", "command": insert_fn},
        {"label": "Delete step", "command": delete_fn},
        {"separator": True},
        {"label": "Move", "items": [
            {"label": "Up",   "command": up_fn},
            {"label": "Down", "command": down_fn},
        ]},
    ])

Passing ``widget`` auto-binds the right-click (``button="<Button-3>"`` by
default); omit it and drive the menu yourself with ``m.show`` /
``m.popup(x, y)``:

.. code-block:: python

    m = ContextMenu(items=[...])
    widget.bind("<Button-3>", m.show)

``items`` may be a list of specs *or* a callable ``(event) -> list``,
re-evaluated on every popup so the menu can reflect what was clicked:

.. code-block:: python

    ContextMenu(canvas, items=lambda e: build_items(step_at(e.y)))

Item spec (the VIStk menu convention shared with ``HostMenu``)::

    {"label": str, "command": callable}              # leaf command
    {"label": str, "items": [<item spec>, ...]}      # cascade submenu
    {"separator": True}                              # separator

Per-item extras: ``"state": "disabled"``, ``"accelerator": str``, and
``"checkbutton": True`` with ``"variable": BooleanVar``. Other keyword
args: ``master`` (Menu parent when no ``widget`` is given), ``tearoff=0``,
``font``, ``button="<Button-3>"``. Method ``set_items(items)`` swaps the
source. Owned menus are destroyed with the bound widget.

----

SettingsWindow / SettingsTab (0.6.0)
------------------------------------

The built-in application-settings surface: a ``ttk.Notebook`` whose first tab
("General") edits the framework's window / host / appearance / notification
preferences, backed by ``Project.Settings``. Both classes share one builder
(``_SettingsUI``) and render the identical surface — they differ only in where it
lives.

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Class
     - Role
   * - ``SettingsTab(host)``
     - The surface as a **tab module** — duck-typed like a screen (``setup(frame)``,
       ``on_quit()``, no ``loop``), so Settings sits in the tab strip like any screen.
       This is what ``Host`` opens. ``base_name = "Settings"`` gives it a stable
       identity for single-instance focus.
   * - ``SettingsWindow(host, parent=None)``
     - The original modal ``tk.Toplevel`` (Save / Cancel / Restore Defaults). Retained
       as a fallback for when there is no chromed window to host a tab, and for callers
       that still construct it directly. Call ``.show()`` to grab input and block until
       it closes.

Neither is normally constructed by application code — ``Host`` opens the surface from
its framework-provided menu entry.

Behaviour
~~~~~~~~~

- Controls are seeded from ``ProjectSettings.effective()``, so each shows its current
  effective value (default *or* override).
- On **Save**, a control whose value equals the framework default is written as a
  *reset* rather than a redundant override, so ``settings.json`` stays minimal; the
  rest are stored and flushed with a single ``ProjectSettings.save()``.
- Blank numeric fields mean "unset"; non-numeric or negative input is rejected silently
  in favour of the stored value rather than corrupting it.
- ``SettingsTab.setup`` may run more than once for one logical tab (VIStk re-runs it
  when a tab is dragged between panes), so it rebuilds and re-seeds from scratch each
  time — unsaved edits are dropped on a move, the same "closing discards" contract as
  the modal window's Cancel.
- Appearance settings are persisted but applied on next launch.

Application panels
~~~~~~~~~~~~~~~~~~

Apps contribute their own tabs with ``host.register_settings_panel(name, setup_fn)``.
Each ``setup_fn`` receives the tab frame and builds into it, mirroring a screen's
``setup``. A panel that raises shows an inline error in its own tab rather than a blank
one.

``setup_fn`` may take **one** argument (the frame — the panel manages its own
persistence) or **two** (``frame, ui``), where *ui* is the settings surface itself. The
two-argument form lets a panel build fields that ride the window's own Save / Restore
Defaults:

.. code-block:: python

    def build_panel(frame, ui):
        ui.add_check(frame, 0, "Enable fast mode", "myapp.fast_mode")
        ui.add_int(frame,   1, "Row height", "myapp.row_height", "px")
        ui.add_combo(frame, 2, "Units", "myapp.units", ["mm", "in"])

    host.register_settings_panel("My App", build_panel)

.. list-table::
   :header-rows: 1
   :widths: 45 55

   * - Method
     - Description
   * - ``add_check(parent, row, label, key)``
     - Checkbox bound to boolean setting *key*.
   * - ``add_int(parent, row, label, key, hint="")``
     - Spinbox bound to integer setting *key* (blank = unset/default). *hint* is grey
       trailing text, e.g. a unit.
   * - ``add_combo(parent, row, label, key, values, editable=False)``
     - Combobox bound to string setting *key*. ``editable=True`` allows free text.

Fields built through these helpers are registered in the surface's read-back registry,
so they are saved, restored and defaulted exactly like the General tab — no per-panel
Save button, and no apply-on-change surprise. The ``ProjectSettings`` storage API and
``Host.register_settings_panel`` are covered in :doc:`structures` and :doc:`objects`.

----

v-prefixed widgets (0.6.0)
--------------------------

A family of widgets that subclass the **classic** tk widgets rather than ttk, so
per-instance ``bg`` / ``fg`` / ``font`` actually work, and that add two things on top:

1. **Parent-property inheritance** — each widget declares which visual options it
   inherits; any the caller omits are filled in from the parent at construction.
   Explicitly-passed options always win. A ``vLabel`` dropped into a white frame is
   white, not default grey.
2. **Optional rounded corners** — opt in with ``radius``. This consolidates the
   hand-rolled Canvas-polygon "pill / chip / card" pattern that screens otherwise
   reimplement one at a time.

At ``radius=0`` (the default) every one of them is a plain native widget with no extra
machinery — they are drop-in replacements.

Hierarchy
~~~~~~~~~

``vWidget`` is a pure mixin (it subclasses ``object``, never ``tk.Widget``) combined with
a native widget through multiple inheritance, so a ``vLabel`` genuinely *is* both a
``vWidget`` and a ``tk.Label``. ``vWidget.__init__`` runs first in the MRO — it computes
inheritance and pops the rounded kwargs — then defers to the native base through
cooperative ``super().__init__()``, so the Tcl widget is created exactly once.

.. code-block:: text

    vLabel(RoundedLeaf, vWidget, Label)
    vButton(RoundedLeaf, vWidget, Button)
    vImage(vWidget, Label)
    vFrame(RoundedContainer, vWidget, LayoutFrame)
    vLabelFrame(RoundedContainer, vWidget, LabelFrame)

``RoundedLeaf`` and ``RoundedContainer`` are internal mixins holding the two rounding
strategies. They are mixed in *before* ``vWidget`` so their render hooks win the MRO.
Leaves round by painting the fill into the widget's single image slot (or, when the
caller needs that slot for their own ``image=``, by overlaying corner tiles); containers
round with a lowered background label plus a child inset. You do not import them
directly — subclass ``vWidget`` if you need a further v-widget of your own.

Shared keyword arguments
~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 25 15 60

   * - Argument
     - Type
     - Description
   * - ``radius``
     - ``int``
     - Corner radius. ``0`` (default) disables all rounded rendering.
   * - ``radius_style``
     - ``str``
     - ``"pixels"`` (default) — *radius* is a pixel value. ``"percent"`` — *radius* is a
       percentage of the maximum round (half the short side), so ``100`` is a full
       pill/circle at any size. Spellings normalise (``"px"``, ``"%"``, ``"percentage"``,
       case-insensitive); an unrecognised value degrades to ``"pixels"``.
   * - ``outline``
     - ``str / None``
     - Stroke colour drawn around the rounded rectangle.
   * - ``outline_width``
     - ``int``
     - Stroke width in px (default ``1``; only used with *outline*).
   * - ``corner_bg``
     - ``str / None``
     - Colour painted outside the corner arc so it blends. Defaults to the parent's
       background. *(Not on* ``vImage`` *, which makes its corners genuinely
       transparent.)*

Radius semantics
~~~~~~~~~~~~~~~~

The radius is resolved by ``effective_radius(radius, style, w, h)`` from the **live**
size inside every render path, not once at construction — so a percentage radius stays
correct through resizes, and the result is always clamped to half the short side. A
radius can therefore never exceed what the widget can actually show.

Common behaviour
~~~~~~~~~~~~~~~~

- **Inheritance is a snapshot** taken at construction. Call ``refresh()`` after the
  parent's appearance changes to re-pull the inherited options (the ones you never set
  explicitly) and repaint.
- **Runtime recolouring works** — ``configure(bg=...)`` repaints the rounded corners
  live; ``vButton`` also repaints on ``state``.
- **The resize repaint is clobber-proof.** It lives on a dedicated bindtag rather than
  an instance binding, so your own ``widget.bind("<Configure>", fn)`` *without*
  ``add="+"`` cannot silently replace it and leave the widget rendering square.
- Parents are read via ``cget`` for classic widgets and ``Style().lookup`` for ttk ones,
  falling back to ``SystemButtonFace``.
- ``help(vLabel)`` lists every native tk option too: the native option block is lifted
  from tkinter's own ``__init__`` docstring at class-creation time, and editors see the
  same set through ``Unpack[TypedDict]`` hints.

.. note::

   Corner blending assumes a **solid-colour parent** — the area outside the arc is
   painted with the parent's background so it blends in. On a gradient or image
   background the corners will not disappear.

Rounded-image helpers
~~~~~~~~~~~~~~~~~~~~~

Exported for direct use when you need the artwork without a v-widget.

.. list-table::
   :header-rows: 1
   :widths: 45 55

   * - Function
     - Description
   * - ``rounded_pil_image(width, height, radius, fill, corner_bg, outline=None, outline_width=0, supersample=4)``
     - Anti-aliased rounded rectangle as a raw ``PIL.Image`` — drawn at
       ``supersample``× resolution and Lanczos-downscaled. Colours are ``(r, g, b)``
       0-255 tuples.
   * - ``make_rounded_image(...)``
     - Same arguments; wraps the result in a ``PIL.ImageTk.PhotoImage``. Keep a
       reference or Tk will garbage-collect it.
   * - ``effective_radius(radius, style, w, h)``
     - Resolve a ``radius``/``radius_style`` pair to a pixel radius for a *w*×*h* box,
       clamped to half the short side.
   * - ``round_image(img, radius, outline=None, outline_width=0, supersample=4)``
     - Return *img* with anti-aliased **transparent** rounded corners and an optional
       stroked outline. The mask is multiplied into the image's own alpha, so existing
       PNG transparency survives.

----

vLabel (0.6.0)
--------------

``vLabel(RoundedLeaf, vWidget, Label)`` — a ``tk.Label`` that inherits ``background``,
``foreground`` and ``font`` from its parent and can be rounded.

.. code-block:: python

    from tkinter import Frame
    from VIStk.Widgets import vLabel

    pane = Frame(root, bg="white")

    vLabel(pane, text="Hello").pack()                      # bg/fg/font inherited
    vLabel(pane, text="Pill", bg="#2f78d3", fg="white",
           radius=100, radius_style="percent").pack()      # full pill
    vLabel(pane, text="Item", image=icon,
           compound="left", radius=8).pack()               # icon laid out natively

Constructor: ``vLabel(master=None, *, radius=0, radius_style="pixels", outline=None,
outline_width=1, corner_bg=None, **label_options)``.

A **text-only** label paints the rounded fill into its image slot and draws the text over
it, so the text is never covered at any radius — circles included. Passing your own
``image=`` switches to corner-tile rounding, which leaves the native image slot free so
``image`` / ``compound`` / ``anchor`` behave exactly as on a native ``Label``. The tiles
are opaque, so keep the radius modest in that mode.

----

vButton (0.6.0)
---------------

``vButton(RoundedLeaf, vWidget, Button)`` — a ``tk.Button`` with the same inheritance and
rounding as ``vLabel``. ``command`` / ``invoke()`` and every native button option pass
through unchanged.

.. code-block:: python

    from VIStk.Widgets import vButton

    vButton(bar, text="Save", command=save).pack()          # bg/fg/font inherited

    vButton(bar, text="Quote", command=quote, radius=8,     # rounded chip
            bg="#eef1f6", fg="#2f78d3",
            active_fill="#dbe6f6").pack()                   # hover fill

Constructor adds two arguments to the shared set:

.. list-table::
   :header-rows: 1
   :widths: 25 15 60

   * - Argument
     - Type
     - Description
   * - ``active_fill``
     - ``str / None``
     - Hover fill colour (rounded mode only), applied on ``<Enter>`` / ``<Leave>``.
   * - ``disabled_fill``
     - ``str``
     - Fill painted when ``state="disabled"`` (default ``"#e9ecef"``). Pair it with
       ``configure(state=...)``.

Rounded mode flattens the relief (``relief="flat"``, ``overrelief="flat"``) and shows a
hand cursor. Disabling the button greys it, swaps the cursor back to an arrow, and gates
the click. In tile mode the corner tiles forward clicks and hover events to the button,
so the rounded corners stay live rather than swallowing them.

----

vFrame (0.6.0)
--------------

``vFrame(RoundedContainer, vWidget, LayoutFrame)`` — a ``LayoutFrame`` (so it keeps the
``.Layout`` helper; see :doc:`objects`) that inherits ``background`` only — frames have
no fg/font — and can be rounded.

.. code-block:: python

    from VIStk.Widgets import vFrame, vLabel

    card = vFrame(root, bg="white", radius=14)              # white card on a grey parent
    card.place(relx=.1, rely=.1, relwidth=.8, relheight=.8)
    card.Layout.colSize([1.0]); card.Layout.rowSize([1.0])
    vLabel(card, text="Inside").place(card.Layout.cell(1, 1))

Constructor adds ``inset`` to the shared set:

.. list-table::
   :header-rows: 1
   :widths: 25 15 60

   * - Argument
     - Type
     - Description
   * - ``inset``
     - ``int / None``
     - Content inset (``.Layout.margin``) in px applied to every child, however it was
       placed. ``None`` (default) auto-computes ``ceil(radius·(1 − 1/√2))`` — the largest
       rectangle that fits inside the corner arc. Pass a larger value to pull content
       further in, or ``0`` for none.

The frame's ``bg`` is the **fill**. A Tk child is an opaque rectangle with no per-widget
transparency, so a child reaching a rounded corner would square it off; that is why every
child is inset — under ``place``, ``pack``, ``grid`` *and* ``.Layout.cell`` alike, with
the caller's own padding preserved. The inset is invisible when the child shares the
frame's fill, which is the inherited default.

Children added at runtime, after the frame has been sized, are picked up on the next
resize; call ``refresh()`` to re-inset them immediately.

----

vLabelFrame (0.6.0)
-------------------

``vLabelFrame(RoundedContainer, vWidget, LabelFrame)`` — a drop-in ``tk.LabelFrame``
(``text``, ``labelanchor``, ``labelwidget``, ``relief``, ``bd`` … all work) that inherits
``background``, ``foreground`` and ``font``, carries a ``.Layout`` like ``vFrame``, and
takes the same ``inset`` argument.

.. code-block:: python

    from VIStk.Widgets import vLabelFrame, vLabel

    box = vLabelFrame(root, text="Tooling", radius=12, outline="#c8ccd2")
    box.place(x=20, y=20, width=260, height=180)
    box.Layout.colSize([1.0]); box.Layout.rowSize([1.0])
    vLabel(box, text="Inside").place(box.Layout.cell(1, 1))

A rounded box almost always wants an ``outline`` (or a fill that contrasts the parent) —
the native rectangular border is flattened in rounded mode, so without one the only thing
drawn is the title.

The title needs special handling: a ``LabelFrame`` lays its children out in a *content
area* below the title band, so a background image placed there would miss the top and
bottom border. In rounded mode the background is floated across the **whole** frame
instead, and the title is routed through a ``labelwidget`` — an internal ``Label``
mirroring your ``text`` / ``fg`` / ``font``, or the ``labelwidget`` you supply — which Tk
still positions per ``labelanchor`` and which is lifted above the background, so the
title breaks the rounded border exactly like a native one. ``configure(text=...)``,
``cget("text")`` and ``box["text"]`` (plus ``fg`` / ``foreground`` / ``font``)
transparently proxy to that title. None of this applies at ``radius=0``.

----

vImage (0.6.0)
--------------

``vImage(vWidget, Label)`` — an **image-only** widget, the mirror of ``vLabel``'s "text
with an optional image". Path resolution and loading are delegated to ``VIMG``, so
``Project().p_images`` lookup, the glob fallback and ``absolute_path`` behave exactly as
everywhere else; ``vImage`` owns only the Tk rendering. It inherits ``background`` only.

.. code-block:: python

    from VIStk.Widgets import vImage

    # Contain a logo in the widget, letterboxed with the inherited bg
    vImage(pane, "logo").place(relwidth=1, relheight=1)

    # A fixed-size rounded thumbnail
    vImage(pane, "avatar.png", size=(64, 64), radius=12).pack()

Constructor: ``vImage(master=None, path=None, *, image=None, absolute_path=False,
size=None, fit=True, resample=Resampling.BICUBIC, radius=0, radius_style="pixels",
outline=None, outline_width=1, **label_options)``.

.. list-table::
   :header-rows: 1
   :widths: 25 15 60

   * - Argument
     - Type
     - Description
   * - ``path``
     - ``str / None``
     - Image path resolved by ``VIMG``. ``None`` builds an empty holder — call
       ``set_path()`` / ``set_image()`` later.
   * - ``image``
     - ``PIL.Image / None``
     - An in-memory image to display instead of loading from disk. Takes precedence over
       *path*.
   * - ``absolute_path``
     - ``bool``
     - Treat *path* as a literal filesystem path (no ``p_images`` lookup).
   * - ``size``
     - ``(w, h) / None``
     - Fixed pixel box to fit into. Omit to fit the **live** widget size, re-fitting on
       every resize.
   * - ``fit``
     - ``str / bool``
     - ``"fit"`` (contain, aspect-preserved, letterboxed — the default), ``"stretch"``
       (fill exactly, ignore aspect), ``"crop"`` (cover, centre-crop the overflow), or
       ``"none"`` (natural size). ``True`` / ``False`` are aliases for ``"fit"`` /
       ``"none"``.
   * - ``resample``
     - ``Resampling``
     - PIL resampling filter, default ``BICUBIC``. Use ``NEAREST`` to keep hard colour
       boundaries crisp when stretching.

Methods: ``set_path(path, *, absolute_path=False)`` swaps the source from disk and
repaints; ``set_image(pil_image)`` swaps to an in-memory image with no disk load. The
loaded ``VIMG`` (when there is one) is exposed as ``.VIMG``.

Rounding here is done image-side rather than with the shared machinery: an anti-aliased
mask makes the corners genuinely **transparent**, so the widget's inherited ``bg`` shows
through and re-blends on a ``bg`` change with no re-render. A percentage radius resolves
against the *rendered* image, so it tracks the picture as it is re-fitted.
