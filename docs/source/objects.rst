Objects
=======

Objects are the core building blocks of a VIStk application. Import from ``VIStk.Objects``.

Root
----

``Root(Tk, Window)`` — The application's main window. Wraps ``Tk`` with VIStk attributes.

See also Host — **not** a subclass of ``Root``, but a standalone coordinator that owns a hidden
``Tk`` root and manages visible windows for it. It adds tabbed screen management, multi-window
lifecycle, and unified navigation. There is no system tray: the Host lives exactly as long as
its windows.

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

The Host is not a background service and there is no system tray — the 0.5.3 always-Host
refactor removed it. The Host starts with the first window and tears itself down once the last
``DetachedWindow`` closes; a localhost socket provides single-instance forwarding while a Host
is alive.

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
   * - ``host.open(screen_name, args=None)``
     - Unified navigation. Tabbed screens open as tabs in the active window; standalone
       screens open as chromeless ``DetachedWindow`` instances. ``args`` are CLI-style tokens
       forwarded to the screen's ``ArgHandler`` before its ``setup()`` runs. Refuses to open a
       screen whose binary is missing from a compiled install, showing an ``InfoRow`` banner
       instead.
   * - ``host.update()``
     - Pumps one iteration: opens the startup screen(s) on the first tick, drains the IPC
       queue, calls ``loop()`` on every open tab, updates Tk, and shuts down when the last
       window closes.
   * - ``host.tick_fps()``
     - Call once per loop iteration to maintain ``host.fps``.
   * - ``host.quit_host()``
     - Closes all ``DetachedWindow`` instances one by one (respecting ``on_quit`` vetoes),
       persists the session, sets ``Active = False``, and destroys the root. A veto aborts the
       shutdown and leaves settings untouched.
   * - ``host.register_settings_panel(name, setup_fn)``
     - Adds a tab named ``name`` to the built-in Settings window. See `Settings panels`_.
   * - ``host.register_menubar_accessory(builder)``
     - Registers a live widget for the menubar's right edge. See `Menubar accessories`_.
   * - ``host.unregister_startup()``
     - Removes the Host from the Windows startup registry (``HKCU\...\CurrentVersion\Run``,
       keyed ``<ProjectTitle>Host``). The matching ``_register_startup()`` is private and
       driven by the ``host.start_with_os`` setting; neither runs automatically on first launch.

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

Settings panels
~~~~~~~~~~~~~~~

``register_settings_panel(name, setup_fn)`` lets an application contribute its own tab to the
framework's Settings window alongside the built-in **General** tab. ``name`` is the notebook tab
label; registering the same name twice replaces the earlier panel. Register before entering the
update loop — typically in ``.VIS/Host.py`` — because the panel list is read each time the
Settings surface is built.

``setup_fn`` receives the tab body (a ``ttk.Frame``) and builds into it, mirroring a screen's
``setup(parent)``. Two arities are accepted:

- ``setup_fn(frame)`` — self-managed. The panel builds its own widgets and reads/writes
  ``host.Project.Settings`` itself.
- ``setup_fn(frame, ui)`` — integrated. ``ui`` is the settings controller; fields built with
  ``ui.add_check(parent, row, label, key)``, ``ui.add_int(parent, row, label, key, hint="")``,
  or ``ui.add_combo(parent, row, label, key, values, editable=False)`` are registered in the
  window's read-back registry and ride its own **Save** and **Restore Defaults** buttons exactly
  like the General tab — no per-panel Save button, no apply-on-change surprise.

.. code-block:: python

    def my_panel(parent, ui):
        ui.add_check(parent, 0, "Enable feature X", "my.feature.enabled")
        ui.add_int(parent, 1, "Retry limit", "my.feature.retries", "attempts")

    host.register_settings_panel("My Plugin", my_panel)

A panel that raises during ``setup_fn`` does not take the Settings window down — the traceback
is printed and the tab shows an inline error message, so a broken panel is visible rather than
blank.

Menubar accessories
~~~~~~~~~~~~~~~~~~~

``register_menubar_accessory(builder)`` registers a **live widget** for the trailing (right) edge
of the menubar. The native OS menubar cannot host Tk widgets, so accessories are mounted instead
in the right-aligned slot of each window's top tab-bar row — the first Tk-controlled strip, which
reads as the menubar's right side.

``builder(parent)`` is called once per window with that slot (a ``tk.Frame`` pinned to the
corner); build a small widget into it. The return value is ignored, and the widget owns its own
refresh (e.g. a ``widget.after`` tick) — the Host does not drive it. Register before entering the
update loop. A vertical tab bar has no accessory slot and is skipped, and a builder that raises is
isolated so it cannot take the window down.

.. code-block:: python

    def user_badge(parent):
        from tkinter import ttk
        ttk.Label(parent, text=current_user()).pack(side="right", padx=6)

    host.register_menubar_accessory(user_badge)

Reach for an accessory only when the content must stay a live widget — an entry, a combobox, an
animation. For a *static* text or bitmap badge, prefer the native menubar path
(``HostMenu.add_project_command`` with a PIL image and/or ``align="right"``), which puts the entry
on the real Windows menu strip rather than in the tab-bar row below it; see :doc:`widgets`.

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

**Hook lookup:** Hooks (``on_focused``, ``on_unfocused``, ``on_quit``, ``configure_menu``,
``has_unsaved``) are read off the tab's own per-tab namespace — the same module that holds the
rest of the screen's API. There is no separate hooks module to consult.

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
one or more ``TabManager`` panes). Every visible application window is a ``DetachedWindow``;
further ones are created by the Host when a standalone screen opens or when a tab is popped out
via the right-click context menu or drag-to-detach. Tracked in ``host.detached_windows``.

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

Window icons (0.6.1)
~~~~~~~~~~~~~~~~~~~~

Windows keeps two icon slots per window — ``ICON_SMALL`` (title bar and alt-tab) and ``ICON_BIG``
(taskbar) — but Tk's ``iconphoto`` fills both with a single image, so before 0.6.1 the two were
always identical. ``DetachedWindow`` now drives them independently.

**Configuration:**

- ``defaults.icon`` in ``project.json`` (read as ``project.d_icon``) — the taskbar icon, and the
  only icon on non-Windows platforms.
- ``defaults.window_icon`` (read as ``project.d_window_icon``) — the title-bar icon. This is the
  **only** project-level way to set it. Leaving it unset preserves the pre-0.6.1 behaviour of one
  shared image.
- A screen's ``icon`` and ``window_icon`` entries override the project defaults, but **only for a
  chromeless (standalone, ``tabbed: false``) window** that the screen owns outright.

All four name a file in the project's ``Icons/`` folder without its extension; any PIL-readable
format works.

**Behaviour:**

- The taskbar slot is filled via ``iconphoto`` exactly as before: a chromeless screen's ``icon``
  if it has one, else ``project.d_icon``.
- The title-bar slot is filled from ``project.d_window_icon``, overridden by a chromeless screen's
  ``window_icon``.
- A tabbed screen can never repaint its window's title-bar icon. Its window is chromed and shared
  with whatever other tabs are open, so the internal icon loader is never handed a screen name for
  it — the constraint is structural, not a runtime check. Set ``defaults.window_icon`` instead.
- The title-bar override is Windows-only: it resolves the window's decorated wrapper HWND and
  sends ``WM_SETICON``. On every other platform it is a no-op and the title bar keeps sharing the
  ``iconphoto`` image.
- The underlying HICON handles are cached process-wide, because ``WM_SETICON`` does not copy the
  icon — the handle must outlive the call. Each distinct icon name is therefore built at most
  once per process.

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
     - Loads ``Icons/<icon>.*`` as the window icon using PIL. Pass the name without extension;
       a name that matches no file prints a warning and leaves the icon untouched.

``setIcon`` uses ``iconphoto``, which fills the title-bar and taskbar slots with the same image.
The independent title-bar icon added in 0.6.1 applies to Host-managed windows only — see
`Window icons (0.6.1)`_.

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

    # Center a popup on its parent window — flicker-free (0.5.0+)
    from VIStk.Objects import WindowGeometry
    WindowGeometry(popup)
    # ... build all child widgets first ...
    popup.WindowGeometry.center_on(root)

.. note::

   The pre-0.5.0 multi-call pattern (``popup.update()`` →
   ``getGeometry(True)`` → ``setGeometry(align="center", ...)``) made the
   popup briefly visible at the OS default position before jumping to
   the centred position.  :meth:`center_on` performs the same math
   inside a ``withdraw()`` / ``deiconify()`` wrap and uses
   ``update_idletasks()`` (layout-only) instead of ``update()``, so the
   window is never drawn at its default position.

   Do not call ``center_on`` on the root ``Tk()`` window — ``withdraw()``
   on the main application window hides it entirely.

center_on (0.5.0)
~~~~~~~~~~~~~~~~~

``center_on(window_ref)``

Centre this window on *window_ref* without a visible flicker.  Drop-in
replacement for the multi-call ``update + getGeometry + setGeometry``
pattern.  Call after all child widgets are built so ``winfo_width`` /
``winfo_height`` reflect the final size.

.. code-block:: python

    popup = Toplevel(root)
    Button(popup, text="OK", command=popup.destroy).pack(padx=50, pady=50)

    from VIStk.Objects import WindowGeometry
    WindowGeometry(popup)
    popup.WindowGeometry.center_on(root)

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


open_active_screen_docs (0.5.0)
-------------------------------

Reads the active screen from the in-process Host singleton, runs
``Project.resolve_docs_url()`` (active screen ``docs`` -> project
``defaults.docs`` -> ``None``), and hands the URL to
:func:`webbrowser.open`.  Returns ``True`` on dispatch, ``False`` if no
URL is configured.

Intended to be wired into ``HostMenu.add_project_command`` for a
one-line top-level Help button:

.. code-block:: python

    from VIStk.Widgets import HostMenu
    from VIStk.Objects import open_active_screen_docs

    host_menu.add_project_command("Help", open_active_screen_docs)

The URL is taken verbatim from ``project.json``; configure entries via
``VIS docs set ...`` (see :doc:`cli`).
