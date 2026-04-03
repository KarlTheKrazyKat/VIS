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

Registry
~~~~~~~~

All live ``TabBar`` instances are tracked in ``VIStk.Widgets._TabBar._TABBAR_REGISTRY``. This
list is used during drag motion to detect cross-bar merges.

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
   * - ``clear_project_items()``
     - Remove all project-layer cascades. Intended for teardown.
   * - ``set_screen_items(items, label="Screen")``
     - Accumulates — adds one cascade to the screen layer. Call multiple times in one
       ``configure_menu`` hook to contribute multiple cascades. All cleared together on
       tab deactivation.
   * - ``clear_screen_items()``
     - Remove all accumulated screen cascades. Called automatically on tab deactivation.

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

    menu = VISMenu(parent_frame, "path/to/menu.json")

----

MenuItem
--------

``MenuItem(Button)`` — A single button used by ``VISMenu``. Can be created directly for
individual menu-style buttons without a full JSON-driven menu.

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

    menu_win = MenuWindow(root, "path/to/menu.json")

----

ScrollMenu
----------

``ScrollMenu(ScrollableFrame)`` — A scrollable ``VISMenu``. Useful when the menu has more
items than can fit on screen.

.. code-block:: python

    from VIStk.Widgets import ScrollMenu

    sm = ScrollMenu(parent, "path/to/menu.json")
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
