Objects
=======

Objects are the core building blocks of a VIStk application. Import from ``VIStk.Objects``.

Root
----

``Root(Tk, Window)`` — The application's main window. Wraps ``Tk`` with VIStk attributes.

See also Host — a subclass of Root that adds persistent tray-based lifecycle, tabbed screen
management, and unified navigation.

.. code-block:: python

    from VIStk.Objects import Root

    root = Root()

**Attributes:**

.. list-table::
   :header-rows: 1
   :widths: 25 20 55

   * - Attribute
     - Type
     - Description
   * - ``root.Active``
     - ``bool``
     - Set to ``False`` to exit the update loop and close the app
   * - ``root.WindowGeometry``
     - ``WindowGeometry``
     - Geometry helper attached to this window
   * - ``root.Layout``
     - ``Layout``
     - Layout manager for this window
   * - ``root.Project``
     - ``Project``
     - The loaded VIS project

**Methods:**

.. list-table::
   :header-rows: 1
   :widths: 45 55

   * - Method
     - Description
   * - ``root.screenTitle(screen, title=None)``
     - Sets the window title and marks the active screen in ``Project``. If ``title`` is omitted,
       the screen name is used.
   * - ``root.unload()``
     - Cleanly destroys all child widgets and sets ``Active = False``. Wired to the window close
       button automatically.
   * - ``root.exitQueue(action, *args, **kwargs)``
     - Registers a function to call after the main loop exits — use for screen redirects.
   * - ``root.exitAct()``
     - Executes the registered exit action.
   * - ``root.fullscreen()``
     - Maximizes the window (zoomed, not absolute fullscreen).
   * - ``root.unfullscreen()``
     - Restores the window to normal size.
   * - ``root.setIcon(icon)``
     - Sets the window icon from ``Icons/<icon>.*``. Pass the name without extension.

**Typical pattern:**

.. code-block:: python

    root = Root()
    root.screenTitle("Home")
    root.WindowGeometry.setGeometry(width=1024, height=768, align="center")
    root.fullscreen()

    # build UI here

    while root.Active:
        root.update()

Host
----

``Host`` — The application host. Owns a hidden ``Tk()`` root window and manages one or more
visible ``DetachedWindow`` instances. The Host is **not** a subclass of ``Root`` — it is a
standalone class that coordinates window lifecycle, screen loading, and menu configuration.

The hidden root is never shown to the user. All visible UI lives inside ``DetachedWindow``
instances, each of which contains its own ``HostMenu``, ``SplitView`` (with ``TabManager``
panes), and ``InfoRow``.

On the first call to ``update()``, the Host automatically opens the project's default screen
(from ``project.json``). This deferred open ensures that ``Host.py`` has time to configure
``default_menu_setup`` before any window is created.

.. code-block:: python

    from VIStk.Objects import Host
    from modules.menu import shared_menu_structure

    host = Host()
    host.default_menu_setup = lambda m: m.build_shared_menu(shared_menu_structure())

    while host.Active:
        host.tick_fps()
        host.update()

**Attributes:**

.. list-table::
   :header-rows: 1
   :widths: 30 20 50

   * - Attribute
     - Type
     - Description
   * - ``host.Active``
     - ``bool``
     - ``True`` while the Host is running. Set to ``False`` by ``quit_host()``.
   * - ``host.root``
     - ``Tk``
     - The hidden Tk root. All ``DetachedWindow`` Toplevels are children of this root.
       Calling ``host.root.update()`` (via ``host.update()``) processes events for every window.
   * - ``host.Project``
     - ``Project``
     - The loaded VIS project.
   * - ``host.detached_windows``
     - ``list[DetachedWindow]``
     - All live DetachedWindow instances.
   * - ``host.registered_tab_managers``
     - ``list[TabManager]``
     - All active TabManager panes across all windows.
   * - ``host.active_tab_manager``
     - ``TabManager / None``
     - The most recently focused pane.
   * - ``host.default_menu_setup``
     - ``callable / None``
     - Called on every new ``DetachedWindow``'s ``HostMenu`` after creation. Set this in
       ``Host.py`` to define project-wide menu items (File, Edit, View, Tools).
   * - ``host.fps``
     - ``float``
     - Current frames per second, updated by ``tick_fps()``.

**Methods:**

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Method
     - Description
   * - ``host.open(screen_name)``
     - Unified navigation. Tabbed screens open as tabs in the active window; standalone
       screens open as new ``DetachedWindow`` instances.
   * - ``host.update()``
     - Processes all pending Tk events for the root and every ``DetachedWindow``. On the
       first call, opens the default screen.
   * - ``host.tick_fps()``
     - Call once per loop iteration to maintain ``host.fps``.
   * - ``host.quit_host()``
     - Closes all ``DetachedWindow`` instances one by one (respecting ``on_quit`` vetoes),
       sets ``Active = False``, and destroys the root.
   * - ``host.unregister_startup()``
     - Removes the Host from the Windows startup registry.

Shared menus
~~~~~~~~~~~~

The Host does not own a menu bar. Each ``DetachedWindow`` creates its own ``HostMenu``. To
define project-wide menus (File, Edit, View, Tools), set ``host.default_menu_setup`` to a
callable that receives a ``HostMenu`` instance:

.. code-block:: python

    host.default_menu_setup = lambda m: m.build_shared_menu({
        "File": [
            {"label": "New", "items": [...]},
            {"separator": True},
            {"label": "Exit", "command": host.quit_host},
        ],
        "Edit": [...],
    })

This callback is invoked on every new window, ensuring consistent menus across all windows.

Singleton
~~~~~~~~~

``Host.__init__`` sets ``VIStk.Objects._Host._HOST_INSTANCE = self``. ``Project.open()`` checks
this reference to route navigation. Only one ``Host`` should exist per process.

TabManager
----------

``TabManager(Frame)`` — Manages the tabbed screen area inside the Host window. Created
automatically by ``Host.__init__`` and exposed as ``host.TabManager``. It owns a ``TabBar`` strip
along the top edge and a content area where each tab's ``Frame`` lives.

Screen modules are imported by the Host and passed to ``open_tab``. ``TabManager`` calls
``setup(frame)``, ``on_focused()``, and ``on_unfocused()`` at the appropriate times.

**Hook lookup priority:** If ``modules/<screen>/m_<screen>.py`` exists, ``TabManager`` checks it
first for ``on_focused``, ``on_unfocused``, and ``configure_menu``. The screen script is used as a
fallback.

**Attributes:**

.. list-table::
   :header-rows: 1
   :widths: 25 20 55

   * - Attribute
     - Type
     - Description
   * - ``tm.tab_bar``
     - ``TabBar``
     - The tab strip widget
   * - ``tm.active``
     - ``str / None``
     - Name of the currently focused tab
   * - ``tm.on_tab_activate``
     - ``callable / None``
     - ``(name, module)`` — called when a tab gains focus
   * - ``tm.on_tab_deactivate``
     - ``callable / None``
     - ``(name / None)`` — called when a tab loses focus
   * - ``tm.on_tab_popout``
     - ``callable / None``
     - ``(name)`` — called when "Open in new window" is requested
   * - ``tm.on_tab_detach``
     - ``callable / None``
     - ``(name)`` — called when a drag is released outside all bars
   * - ``tm.on_tab_refresh``
     - ``callable / None``
     - ``(name)`` — called when "Force refresh" is requested

**Methods:**

.. list-table::
   :header-rows: 1
   :widths: 40 15 45

   * - Method
     - Returns
     - Description
   * - ``open_tab(name, module, hooks=None, icon=None, insert_idx=-1)``
     - ``bool``
     - Open a new tab. If already open, focuses it instead. ``insert_idx`` positions the tab
       (0-based; -1 appends).
   * - ``close_tab(name)``
     - ``bool``
     - Close the named tab, running ``on_unfocused`` first.
   * - ``focus_tab(name)``
     - ``bool``
     - Focus the named tab.
   * - ``has_tab(name)``
     - ``bool``
     - Whether a tab with this name is open.
   * - ``force_refresh_tab(name)``
     - ``bool``
     - Close and reopen at the same position, re-running ``setup(parent)``.
   * - ``set_tab_info(frame, text_or_var)``
     - ``None``
     - Set the info string for the tab. Accepts a plain string or ``tk.StringVar``.

``TabManager`` is not normally used directly — ``host.open()`` handles all navigation.

DetachedWindow
--------------

``DetachedWindow`` — A floating ``Toplevel`` window containing its own ``SplitView`` (which wraps
one or more ``TabManager`` panes). Created by the Host when a tab is popped out via the right-click
context menu or drag-to-detach. Tracked in ``host._detached``.

Popping a tab out re-runs ``setup(parent)`` in the new window, so screen UI state is reset.

**Attributes:**

- ``dw._split_view`` — ``SplitView`` managing the window's content area
- ``dw.tab_manager`` — property returning ``dw._split_view.focused_pane``
- ``dw.HostMenu`` — menu bar (shared cascades cloned from Host)
- ``dw.InfoRow`` — status bar

**Behaviour:**

- Right-clicking a tab and choosing **Open in new window** sends the tab back to the main Host.
- Dragging a tab and releasing it outside all bars creates a new ``DetachedWindow``.
- Dragging a tab from one bar into another registered ``TabBar`` merges it there.
- Dragging a tab into a split zone (edge or center) of any pane in any window creates a split
  or adds the tab to the target pane — cross-window drag-to-split is fully supported.
- **Force refresh** re-imports the screen module and re-runs ``setup(parent)`` in-place.
- Closing the window runs ``on_unfocused`` on all tabs across all panes and destroys them.
- When the Host shuts down, all ``DetachedWindow`` instances are closed first.

``DetachedWindow`` is created internally — you do not instantiate it directly.

SubRoot
-------

``SubRoot(Toplevel, Window)`` — A popup or secondary window. Wraps ``Toplevel`` with VIStk
attributes.

.. code-block:: python

    from VIStk.Objects import SubRoot

    popup = SubRoot()

**Attributes:**

.. list-table::
   :header-rows: 1
   :widths: 25 20 55

   * - Attribute
     - Type
     - Description
   * - ``popup.WindowGeometry``
     - ``WindowGeometry``
     - Geometry helper for this window
   * - ``popup.Layout``
     - ``Layout``
     - Layout manager for this window
   * - ``popup.modal``
     - ``bool``
     - ``True`` if ``modalize()`` has been called

**Methods:**

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Method
     - Description
   * - ``popup.modalize()``
     - Makes the window modal — blocks input to the parent until this window is closed. Cannot be
       undone.

``QuestionWindow`` and ``WarningWindow`` are both subclasses of ``SubRoot``.

Window
------

``Window`` is a mixin class inherited by both ``Root`` and ``SubRoot``. It provides fullscreen
control and icon loading. You do not instantiate it directly.

**Methods:**

.. list-table::
   :header-rows: 1
   :widths: 35 65

   * - Method
     - Description
   * - ``fullscreen(absolute=False)``
     - Maximizes the window. ``absolute=False`` uses OS maximize; ``absolute=True`` uses true
       fullscreen with no title bar.
   * - ``unfullscreen(absolute=False)``
     - Restores window size.
   * - ``setIcon(icon)``
     - Loads ``Icons/<icon>.*`` as the window icon using PIL.

WindowGeometry
--------------

``WindowGeometry`` handles window sizing and positioning. It is automatically attached to ``Root``
and ``SubRoot`` as ``self.WindowGeometry``.

getGeometry
~~~~~~~~~~~

``getGeometry(respect_size=False)``

Reads the current geometry from the window and stores it internally. If ``respect_size=True``,
uses the actual rendered size (``winfo_width/height``) instead of the geometry string.

setGeometry
~~~~~~~~~~~

``setGeometry(width, height, x, y, align, size_style, window_ref)``

Positions and sizes the window.

.. list-table::
   :header-rows: 1
   :widths: 20 20 60

   * - Parameter
     - Type
     - Description
   * - ``width``
     - ``int``
     - Width in pixels (or percentage if ``size_style`` is set)
   * - ``height``
     - ``int``
     - Height in pixels (or percentage if ``size_style`` is set)
   * - ``x``
     - ``int``
     - X position in pixels. Ignored if ``align`` is set.
   * - ``y``
     - ``int``
     - Y position in pixels. Ignored if ``align`` is set.
   * - ``align``
     - ``str``
     - Named alignment: ``"center"``, ``"n"``, ``"ne"``, ``"e"``, ``"se"``, ``"s"``, ``"sw"``,
       ``"w"``, ``"nw"``
   * - ``size_style``
     - ``str``
     - ``"pixels"`` (default), ``"screen_relative"``, or ``"window_relative"``
   * - ``window_ref``
     - ``Tk / Toplevel``
     - Reference window for ``"window_relative"`` sizing

**Examples:**

.. code-block:: python

    # Center an 800x600 window on screen
    root.WindowGeometry.setGeometry(width=800, height=600, align="center")

    # Center a popup on its parent window
    popup.update()
    popup.WindowGeometry.getGeometry(True)
    popup.WindowGeometry.setGeometry(
        width=popup.winfo_width(),
        height=popup.winfo_height(),
        align="center",
        size_style="window_relative",
        window_ref=root
    )

stripGeometry
~~~~~~~~~~~~~

``stripGeometry(objects)``

Returns raw integer values from the current geometry string.

.. code-block:: python

    x, y = root.WindowGeometry.stripGeometry(("x", "y"))
    w, h, x, y = root.WindowGeometry.stripGeometry("all")

Layout
------

``Layout`` is a proportional grid system for placing frames inside a window or frame using
``place()``. Rows and columns are defined as fractions that sum to 1.0.

.. code-block:: python

    from VIStk.Objects import Layout

    layout = Layout(frame)
    layout.rowSize([0.1, 0.8, 0.1])      # 10% header, 80% body, 10% footer
    layout.colSize([0.25, 0.75])          # 25% sidebar, 75% content

rowSize
~~~~~~~

``rowSize(rows, minsize=None, maxsize=None)``

Sets row proportions. Each value is a float from 0.0 to 1.0; they must sum to exactly 1.0.
``minsize`` and ``maxsize`` are optional lists of pixel constraints stored as ``row_min`` /
``row_max``.

.. code-block:: python

    layout.rowSize([0.5, 0.5])
    layout.rowSize([0.1, 0.7, 0.2])
    layout.rowSize([0.1, 0.8, 0.1], minsize=[30, 100, 30])

colSize
~~~~~~~

``colSize(columns, minsize=None, maxsize=None)``

Sets column proportions. Same rules as ``rowSize``. Optional ``minsize`` / ``maxsize`` stored as
``col_min`` / ``col_max``.

.. code-block:: python

    layout.colSize([1.0])
    layout.colSize([0.3, 0.7])
    layout.colSize([0.25, 0.75], minsize=[150, None])

cell
~~~~

``cell(row, column, rowspan=None, columnspan=None, padding=0)``

Returns a ``dict`` of ``place()`` kwargs for the given cell. Pass directly to
``widget.place(**...)``. Rows and columns are 0-indexed. The optional ``padding`` argument adds
inward pixel padding on all sides.

.. code-block:: python

    header = Frame(root)
    header.place(**root.Layout.cell(0, 0))

    # Span multiple cells
    panel = Frame(root)
    panel.place(**root.Layout.cell(1, 0, columnspan=2))

    # 8px padding inside the cell
    card = Frame(root)
    card.place(**root.Layout.cell(1, 1, padding=8))

apply
~~~~~

``apply(widget, row, col, rowspan=None, columnspan=None, padding=0)``

Places ``widget`` in the given cell using absolute pixel coordinates and automatically re-places it
whenever the parent frame is resized. Unlike ``cell()``, ``apply()`` enforces any ``minsize`` /
``maxsize`` constraints set via ``rowSize()`` / ``colSize()``.

.. code-block:: python

    layout.rowSize([0.1, 0.8, 0.1], minsize=[30, 100, 30])
    layout.colSize([0.3, 0.7])

    layout.apply(header_frame, row=0, col=0)
    layout.apply(body_frame,   row=1, col=0, rowspan=1)

``Layout`` is available on ``Root`` as ``root.Layout`` and on ``SubRoot`` as ``popup.Layout``. It
is also the basis for ``LayoutFrame``.

LayoutFrame
-----------

``LayoutFrame(Frame)`` — A standard Tkinter ``Frame`` with a ``Layout`` object pre-attached as
``self.Layout``. Use it when you need to subdivide a frame using proportional placement.

.. code-block:: python

    from VIStk.Widgets import LayoutFrame

    main_area = LayoutFrame(root)
    main_area.place(**root.Layout.cell(1, 0))

    main_area.Layout.colSize([0.4, 0.6])
    main_area.Layout.rowSize([1.0])

    left_panel = Frame(main_area)
    left_panel.place(**main_area.Layout.cell(0, 0))

    right_panel = Frame(main_area)
    right_panel.place(**main_area.Layout.cell(0, 1))

VIMG
----

``VIMG`` loads and optionally auto-resizes images for Tkinter widgets using PIL. Images are loaded
from the project's ``Images/`` folder by default.

.. code-block:: python

    from VIStk.Objects import VIMG

    img = VIMG(label_widget, "logo.png")
    label_widget.configure(image=img.holder.image)

**Constructor:**

.. list-table::
   :header-rows: 1
   :widths: 20 20 60

   * - Parameter
     - Type
     - Description
   * - ``holder``
     - ``Widget``
     - The widget that will display the image
   * - ``path``
     - ``str``
     - Filename in ``Images/``, or an absolute path if ``absolute_path=True``
   * - ``absolute_path``
     - ``bool``
     - If ``True``, ``path`` is treated as a full filesystem path
   * - ``size``
     - ``tuple[int,int]``
     - Fixed ``(width, height)`` in pixels. If ``None``, uses the image's native size.
   * - ``fill``
     - ``Widget``
     - If provided, the image resizes to fit this widget whenever it is resized.

**Auto-resize example:**

.. code-block:: python

    # Image fills a label and resizes with the window
    img_label = Label(root)
    img_label.place(**root.Layout.cell(0, 0))

    img = VIMG(img_label, "background", fill=img_label)

ArgHandler
----------

``ArgHandler`` parses command-line arguments passed to a screen script. Each flag is registered
with a keyword and a callback function. Flags are passed with ``--`` on the command line.

.. code-block:: python

    from VIStk.Objects import ArgHandler
    import sys

    handler = ArgHandler()
    handler.newFlag("load", lambda args: load_record(args[0]))
    handler.newFlag("mode", lambda args: set_mode(args[0]))
    handler.handle(sys.argv)

**Command line usage:**

.. code-block:: text

    python myscreen.py --load 1042 --mode readonly

**Methods:**

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Method
     - Description
   * - ``newFlag(keyword, method)``
     - Registers a flag. Accepts ``Keyword``, ``keyword``, ``K``, or ``k`` on the command line.
       Raises ``KeyError`` if the first letter conflicts with an existing flag.
   * - ``handle(args)``
     - Parses ``sys.argv`` (or any list) and calls the registered method for each ``--flag``
       found, passing the remaining tokens as a list.

The ``ArgHandler`` on ``Root.Project`` is used internally by the CLI for screen loading with
arguments.
