Changelog and Roadmap
=====================

Released
--------

0.4.2 Menus
~~~~~~~~~~~

Three-layer menubar model
^^^^^^^^^^^^^^^^^^^^^^^^^

The ``HostMenu`` menubar is now structured as three permanent layers in order:

1. **Built-in layer** — the "App" cascade (Close Window / Quit), always first, built automatically by ``attach()``
2. **Project layer** — app-wide cascades defined once in ``Host.py`` at startup; never cleared during normal use
3. **Screen layer** — cascades contributed by the active tab via ``configure_menu(menubar)``; all cleared automatically on tab deactivation

``HostMenu`` changes
^^^^^^^^^^^^^^^^^^^^

- ``set_project_items(items, label)`` — new method; appends one cascade to the project layer
- ``clear_project_items()`` — removes all project-layer cascades
- ``set_screen_items(items, label)`` — behaviour change: **accumulates** rather than replaces
- ``clear_screen_items()`` — now removes **all** accumulated screen cascades

``VIS add screen <name> menu <menuname>``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

- ``Screen.addMenu(menu)`` implemented (was a stub)
- Creates ``modules/<screen>/m_<menuname>.py`` with a ``configure_menu(menubar)`` function
- Auto-wires into the hooks module if one exists

Installer & Release fixes
^^^^^^^^^^^^^^^^^^^^^^^^^

- Replaced ``from tkinter import *`` with ``import tkinter as tk`` in ``Installer.py``
- Fixed ``shortcut()``: used stale loop variable and called nonexistent ``user_desktop_dir()``
- Removed stale ``i_file.close()`` in ``makechecks``
- Fixed ``extal()``: only ``chmod +x`` actual binaries on Linux
- Replaced ``os.mkdir`` with ``os.makedirs(exist_ok=True)`` in ``adjacents()``
- Deduplicated ``installables`` list to prevent duplicate checkboxes
- Replaced ``source.index(i)`` with ``enumerate`` in ``makechecks``
- Added ``archive.close()`` calls in quiet mode exit and GUI close button
- Fixed prefix matching in extraction to prevent false matches
- Fixed ``_internal`` filter to use trailing slash
- Fixed ``previous()`` crash via ``global next_btn``
- Replaced four redundant extraction loops with a single-pass install + progress bar UI
- Added version display in installer header and next to checkboxes
- Fixed ``binstall()`` to take a separate ``selected_screens`` parameter
- Replaced manual argument parsing with ``ArgHandler``; added ``--Help``, ``--Path``, and ``--Desktop`` flags
- ``--Quiet`` with no screen names now defaults to installing all screens
- Added ``binaries.zip`` existence check with user-friendly error
- Fixed ``newVersion()`` in ``_Release.py``: compared Version object vs string
- Added user confirmation prompt in ``newVersion()`` before applying a version change
- Re-enabled ``newVersion()`` call in ``release()`` (was commented out)
- Collapsed duplicated path logic in ``clean()``
- Removed ``os.chdir()`` from ``release()``

Cached installer builds
^^^^^^^^^^^^^^^^^^^^^^^

- ``_Release.py`` no longer runs PyInstaller for the installer on every release
- Base installer exe compiled once and cached in ``.VIS/cache/``
- SHA-256 hash of ``Installer.py`` + icon file stored alongside the cache

Planned
^^^^^^^

- Auto-launch after install — optional checkbox on the completion page

----

0.4.1 Screen Management
~~~~~~~~~~~~~~~~~~~~~~~

Single-instance screens
^^^^^^^^^^^^^^^^^^^^^^^^

- New ``single_instance`` boolean field in each screen's ``project.json`` entry (default ``false``)
- ``Screen.__init__`` reads and exposes ``screen.single_instance``
- When ``Host.open()`` is called for a screen with ``single_instance: true`` that is already open, the existing tab is focused rather than creating a new instance
- Set via ``VIS edit <screenname> single_instance true``

``VIS rename <screenname> <newname>``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

- Validates ``newname`` against the same rules as ``VIS add screen``
- Renames the key in ``project.json → Screens``
- Renames the script file if it matches the old name pattern; updates the ``script`` field
- Renames ``Screens/<oldname>/`` → ``Screens/<newname>/``
- Renames ``modules/<oldname>/`` → ``modules/<newname>/``
- Rewrites all import references in the screen script
- Updates ``default_screen`` in ``project.json`` if it matches the old name
- Runs ``stitch`` automatically after rename

``VIS edit <screenname> <attribute> <value>``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

- Directly sets any attribute in the screen's ``project.json`` subdictionary
- Editable attributes: ``script``, ``release``, ``icon``, ``desc``, ``tabbed``, ``single_instance``, ``version``, ``current``
- Type coercion applied automatically by attribute
- Rejects unknown attribute names with a clear error

----

0.4.0 Host and Tabbed Screens
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Host object
^^^^^^^^^^^

- ``Host`` — persistent ``Root`` subclass; hides to system tray on window close; never destroys
- Host registers itself in the Windows startup registry on first run
- Thread-safe cross-thread call queue polled by ``_poll_main_queue``; pystray and IPC threads never call Tkinter directly

TabManager and TabBar
^^^^^^^^^^^^^^^^^^^^^

- ``TabManager`` object — ``Frame`` subclass that owns the tab strip and content area
- ``TabBar`` widget — row of clickable tabs; flat buttons with configurable background colours; active/inactive/hover states; close button per tab
- Tab buttons show screen icon (16×16) to the left of the screen name when configured
- Full hover behaviour: hovering the tab name changes both the name and close button

Screen navigation
^^^^^^^^^^^^^^^^^

- ``host.open(screen)`` — unified navigation; tabbed screens open as Frame tabs; standalone screens open as Toplevel windows
- ``TabManager.open_tab`` / ``TabManager.close_tab`` — full tab lifecycle with ``setup()``, ``on_activate()``, ``on_deactivate()`` hooks
- ``__VIS_CLOSE__:<name>`` IPC message — a screen can ask the Host to close itself

IPC
^^^

- ``send_to_host(project_title, message)`` — sends any message to a running Host via localhost TCP
- Host writes its port to ``%TEMP%/<ProjectTitle>_vis_host.port`` on startup

Tab drag-to-reorder
^^^^^^^^^^^^^^^^^^^

- Tabs can be dragged left or right to change their display order
- An 8-pixel motion threshold distinguishes a drag from a click

InfoRow widget
^^^^^^^^^^^^^^

- Left: active screen name and version
- Centre: project copyright string
- Right: live FPS counter

Layout constraint enforcement
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

- New ``Layout.apply(widget, row, col, ...)`` method places a widget with absolute pixel coordinates and re-places it automatically on every parent ``<Configure>`` event

Tab right-click context menu
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

- **Open in new window**, **Force refresh**, and **Close**

Tab drag-to-detach / merge
^^^^^^^^^^^^^^^^^^^^^^^^^^^

- Releasing a dragged tab outside all registered ``TabBar`` instances creates a new ``DetachedWindow``
- Releasing over a different ``TabBar`` merges the tab there

DetachedWindow
^^^^^^^^^^^^^^

- New class — wraps a ``Toplevel`` + ``TabManager`` for popped-out or drag-detached tabs

Drag ghost window and insertion indicator
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

- Semi-transparent ghost ``Toplevel`` follows the cursor during drag
- Thin coloured vertical insertion indicator shows where the tab will land

Per-screen characteristic info (``set_tab_info``)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

- ``TabManager.set_tab_info(name, text_or_var)`` — set a characteristic string for a tab; accepts a plain ``str`` or a ``tk.StringVar``
- StringVar traces are removed automatically when the tab closes

Dependencies added
^^^^^^^^^^^^^^^^^^

- ``pystray`` — cross-platform system tray support

----

0.3 Release
~~~~~~~~~~~

Releasing
^^^^^^^^^

- Added release command to release version of project
- Using internal ``project.json`` to build spec file to create release
- Can switch from Screen to Screen using internal methods
- Can release single Screen
- Releasing creates Installers for the project

Screen Functionality
^^^^^^^^^^^^^^^^^^^^

- Default Form Changed
- Currently active Screen is tracked
- Can load with args

Objects
^^^^^^^

- VIMG can bind image path resizing to widget

Widgets (new)
^^^^^^^^^^^^^

- Window
- Root Widget (Tk, Window)
- SubRoot Widget (TopLevel, Window)
- WindowGeometry
- LayoutFrame (ttk.Frame)
- QuestionWindow (SubRoot)
- ScrollableFrame (ttk.Frame)
- ScrollMenu (ScrollableFrame)

Widgets (updated)
^^^^^^^^^^^^^^^^^

- Menu: buttons highlight on hover; can provide screennames instead of paths
- MenuItem: now menuitem is the button and text autosizes; will use ``screen.load()`` if provided with screenname

----

Upcoming
--------

0.4.3 Split Layouts, Installer Uninstaller & Install Log
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

- Allow the Host window's content area to be divided into multiple panes with a draggable sash
- **``SplitView`` widget** — replaces the single ``TabManager`` in ``Host``; supports arbitrary split arrangements
- **Uninstaller** — reads ``.VIS/install_log.json`` to remove all installed files and shortcuts
- **Install log** — Installer writes ``.VIS/install_log.json`` after a successful install

0.4.4 Tab Bar Enhancements, Installer Update & Integrity
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

- Tab bar position — top, left, bottom, or right
- Maximum simultaneous open tabs
- Close confirmation for unsaved state
- Update-in-place / patch installer
- Rollback on failure
- Post-install integrity check

0.4.5 Installer Polish
~~~~~~~~~~~~~~~~~~~~~~~

- License / EULA page
- Silent progress output in ``--Quiet`` mode
- Custom installer icon via ``project.json``

0.5.X VIS Widgets
~~~~~~~~~~~~~~~~~

- ``Tooltip`` — hover tooltip
- ``CollapsibleFrame`` — frame with toggle button
- ``AutocompleteEntry`` — Entry with filtered dropdown
- ``DateEntry`` — date input with calendar picker
- Color palette feature

0.6.X Application Settings
~~~~~~~~~~~~~~~~~~~~~~~~~~~

- Settings stored per-project in ``.VIS/settings.json``
- Default window size, alignment, and minimum size
- Remember open tabs; restore on next open
- Built-in settings panel in HostMenu

0.7.X Defaults, Navigation, and Updating Tools
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

- Modify default imports and templates
- Enable/Disable Keyboard Navigation
- Update tools for VIS and binary updates

0.8.X Advanced Creation and Restoration
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

- Create VIS project in new folder
- Default ``.gitignore`` for VIS projects
- Repair broken screens

0.9.X Notifications
~~~~~~~~~~~~~~~~~~~~

- ``Toast`` — non-blocking status overlay that auto-dismisses

1.0.0 Full Release
~~~~~~~~~~~~~~~~~~

- Tkinter styles
- Sample VIS programs
