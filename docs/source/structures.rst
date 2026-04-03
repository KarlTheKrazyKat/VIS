Structures
==========

Structures manage the project registry, screen lifecycle, and release pipeline. Most are used
internally by the CLI and by ``Root``/``Screen.load()``. Import from ``VIStk.Structures``.

VINFO
-----

``VINFO`` is the base class for ``Project`` and ``Screen``. It locates the ``.VIS/`` folder by
walking up the directory tree from the current working directory, and exposes path constants for
all project directories.

You do not instantiate ``VINFO`` directly. It is initialized automatically when ``Project()`` or
``Root()`` is created.

If no ``.VIS/`` folder exists when ``VINFO`` is initialized (i.e., running ``VIS new``), it
creates the project structure and prompts for project name, company, and version.

**Path attributes (available on ``Project`` and ``Screen``):**

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Attribute
     - Description
   * - ``p_project``
     - Absolute path to the project root
   * - ``p_vinfo``
     - Path to ``.VIS/``
   * - ``p_sinfo``
     - Path to ``.VIS/project.json``
   * - ``p_screens``
     - Path to ``Screens/``
   * - ``p_modules``
     - Path to ``modules/``
   * - ``p_templates``
     - Path to ``.VIS/Templates/``
   * - ``p_icons``
     - Path to ``Icons/``
   * - ``p_images``
     - Path to ``Images/``
   * - ``p_vis``
     - Path to the installed VIStk package
   * - ``title``
     - Project name (from ``project.json``)
   * - ``Version``
     - Project ``Version`` object
   * - ``company``
     - Company name (from ``project.json``)
   * - ``copyright``
     - Copyright string; defaults to ``company`` if not set
   * - ``default_screen``
     - Name of the default screen; ``None`` if not set

**Methods:**

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Method
     - Description
   * - ``restoreAll()``
     - Undoes screen isolation — restores all screens that were temporarily set to
       non-releasing during a single-screen release.

Project
-------

``Project(VINFO)`` — Loads the project registry from ``project.json`` and provides screen
management. Automatically attached to ``Root`` as ``root.Project``.

.. code-block:: python

    from VIStk.Structures import Project

    project = Project()

**Attributes:**

.. list-table::
   :header-rows: 1
   :widths: 30 20 50

   * - Attribute
     - Type
     - Description
   * - ``project.screenlist``
     - ``list[Screen]``
     - All registered screens
   * - ``project.Screen``
     - ``Screen``
     - The currently active screen (set by ``screenTitle``)
   * - ``project.d_icon``
     - ``str``
     - Default icon name
   * - ``project.dist_location``
     - ``str``
     - Output folder for releases
   * - ``project.hidden_imports``
     - ``list[str]``
     - PyInstaller hidden imports
   * - ``project.copyright``
     - ``str``
     - Copyright string from ``project.json`` metadata
   * - ``project.host_script``
     - ``str``
     - Filename of the Host entry-point script
   * - ``project.default_screen``
     - ``str / None``
     - Name of the default screen; ``None`` if not set

**Methods:**

.. list-table::
   :header-rows: 1
   :widths: 35 15 50

   * - Method
     - Returns
     - Description
   * - ``hasScreen(name)``
     - ``bool``
     - Checks if a screen with the given name is registered
   * - ``getScreen(name)``
     - ``Screen / None``
     - Returns the ``Screen`` object for the given name
   * - ``verScreen(name)``
     - ``Screen``
     - Returns the screen if it exists, or creates it via ``newScreen``
   * - ``setScreen(name)``
     - ``None``
     - Sets ``self.Screen`` to the named screen
   * - ``load(name, *args)``
     - ``None``
     - Calls ``Screen.load(*args)`` for the named screen (always ``os.execl``)
   * - ``open(name, stay_open=False)``
     - ``None``
     - Unified navigation — routes through Host if running, else ``os.execl``
   * - ``reload()``
     - ``None``
     - Reloads the currently active screen
   * - ``getInfo()``
     - ``str``
     - Returns ``"ProjectName ScreenName Version"`` as a string
   * - ``newScreen(name)``
     - ``int``
     - Interactively creates a new screen (CLI use)
   * - ``set_default_screen(name)``
     - ``bool``
     - Sets the default screen and persists to ``project.json``
   * - ``rename_screen(old, new)``
     - ``int``
     - Renames a screen throughout the project; returns ``1`` on success
   * - ``edit_screen(name, attr, value)``
     - ``int``
     - Sets any attribute in a screen's entry with type coercion; returns ``1`` on success

``open(name, stay_open=False)``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Preferred navigation method when a Host may be running. Routing rules:

- **Host running + target is tabbed** — opens or focuses the tab in the Host window.
- **Host running + target is standalone, ``stay_open=False``** — Host spawns a subprocess;
  the caller should close.
- **Host running + target is standalone, ``stay_open=True``** — Host spawns a subprocess;
  caller keeps running.
- **No Host** — falls back to ``Screen.load()`` (``os.execl``), preserving standalone
  behaviour.

.. code-block:: python

    # Prefer open() over load() for portable navigation
    root.Project.open("WorkOrders")
    root.Project.open("Settings", stay_open=True)

Screen
------

``Screen(VINFO)`` — Represents one screen in the project. Stores metadata and provides the
``load()`` method that switches to this screen.

**Attributes:**

.. list-table::
   :header-rows: 1
   :widths: 30 20 50

   * - Attribute
     - Type
     - Description
   * - ``screen.name``
     - ``str``
     - Screen name
   * - ``screen.script``
     - ``str``
     - Python script filename (e.g. ``"wo.py"``)
   * - ``screen.release``
     - ``bool``
     - Whether this screen is compiled to its own binary
   * - ``screen.icon``
     - ``str / None``
     - Icon name for this screen
   * - ``screen.desc``
     - ``str``
     - Screen description
   * - ``screen.s_version``
     - ``Version``
     - Screen-specific version number
   * - ``screen.path``
     - ``str``
     - Absolute path to ``Screens/<name>/``
   * - ``screen.m_path``
     - ``str``
     - Absolute path to ``modules/<name>/``
   * - ``screen.tabbed``
     - ``bool``
     - If ``True``, opens as a Host tab; if ``False``, runs as a subprocess
   * - ``screen.single_instance``
     - ``bool``
     - If ``True``, ``Host.open()`` focuses the existing tab instead of opening a duplicate

**Methods:**

.. list-table::
   :header-rows: 1
   :widths: 35 65

   * - Method
     - Description
   * - ``screen.load(*args)``
     - Switches to this screen. Routes via IPC if a Host is running; falls back to
       ``os.execl``.
   * - ``screen.close()``
     - Asks the Host to close this screen via IPC. Returns ``True`` if delivered.
   * - ``screen.addElement(name)``
     - Creates ``f_<name>.py`` and ``m_<name>.py`` from templates
   * - ``screen.addMenu(name)``
     - Creates ``modules/<screen>/m_<name>.py`` with a ``configure_menu`` stub
   * - ``screen.stitch()``
     - Rewrites import blocks in the screen script to include all ``f_*`` and ``m_*`` files
   * - ``screen.getModules(script)``
     - Returns all ``Screens.*`` and ``modules.*`` imports found in the script, recursively
   * - ``screen.isolate()``
     - Temporarily disables release for all other screens
   * - ``screen.sendNotification(message)``
     - Sends a desktop notification for this app/screen

Host hooks
~~~~~~~~~~

When ``screen.tabbed`` is ``True``, the Host imports the screen module and calls the following
functions. All hooks have default no-op stubs in the template.

**Lookup priority:** If ``modules/<screen>/m_<screen>.py`` exists, the Host looks for hooks
there first. The screen script is used as a fallback.

.. list-table::
   :header-rows: 1
   :widths: 20 35 45

   * - Hook
     - Signature
     - When called
   * - ``setup``
     - ``setup(parent: Frame)``
     - Once, when the tab is first opened. Build all widgets into ``parent``.
   * - ``configure_menu``
     - ``configure_menu(menubar: HostMenu)``
     - Each time the tab gains focus.
   * - ``on_focused``
     - ``on_focused()``
     - Each time the tab gains focus.
   * - ``on_unfocused``
     - ``on_unfocused()``
     - Each time the tab loses focus or is closed.

.. code-block:: python

    def setup(parent):
        Label(parent, text="Hello from Tab").pack()

    def configure_menu(menubar):
        menubar.set_screen_items([
            {"label": "Refresh", "command": refresh},
            {"separator": True},
            {"label": "Export", "command": export},
        ], label="MyScreen")

    def on_focused():
        start_polling()

    def on_unfocused():
        stop_polling()

IPC — send_to_host
------------------

When the Host is running, any script in the same project can open a screen or send control
messages by calling ``send_to_host()`` directly.

.. code-block:: python

    from VIStk.Structures import send_to_host

    # Open a screen in the running Host
    send_to_host("MyApp", "WorkOrders")

    # Send the quit signal to stop the Host
    send_to_host("MyApp", "__VIS_QUIT__")

    # Close a specific screen
    send_to_host("MyApp", "__VIS_CLOSE__:Settings")

**Parameters:**

.. list-table::
   :header-rows: 1
   :widths: 25 15 60

   * - Parameter
     - Type
     - Description
   * - ``project_title``
     - ``str``
     - The project ``title`` as stored in ``project.json``
   * - ``message``
     - ``str``
     - Screen name to open, or a reserved control message

Returns ``True`` if the message was delivered, ``False`` if no Host port file was found or the
connection failed.

**Reserved control messages:**

.. list-table::
   :header-rows: 1
   :widths: 35 65

   * - Message
     - Effect
   * - ``"__VIS_QUIT__"``
     - Gracefully shuts down the Host
   * - ``"__VIS_CLOSE__:<name>"``
     - Asks the Host to close the named tab or Toplevel

``Screen.close()`` is a convenience wrapper around the ``__VIS_CLOSE__`` message:

.. code-block:: python

    project = Project()
    project.getScreen("Settings").close()

**How it works:** The Host writes its TCP port number to ``%TEMP%/<ProjectTitle>_vis_host.port``
on startup and deletes it on shutdown. ``send_to_host()`` reads that file, connects to
``127.0.0.1:<port>``, and sends the message as UTF-8 text.

Version
-------

``Version`` stores a semantic version number as ``major.minor.patch``.

.. code-block:: python

    from VIStk.Structures import Version

    v = Version("1.3.2")
    print(v)           # "1.3.2"
    v.minor()
    print(v)           # "1.4.0"

**Methods:**

.. list-table::
   :header-rows: 1
   :widths: 20 80

   * - Method
     - Description
   * - ``major()``
     - Increments major, resets minor and patch to 0
   * - ``minor()``
     - Increments minor, resets patch to 0
   * - ``patch()``
     - Increments patch

Release
-------

``Release(Project)`` — Manages the build and release pipeline. Used internally by
``VIS release``. You do not normally instantiate this directly.

.. code-block:: python

    from VIStk.Structures import Release

    rel = Release(flag="beta", type="Minor")
    rel.release()       # build spec, run PyInstaller, bundle assets, create installer
    rel.restoreAll()    # undo any screen isolation

**Methods:**

.. list-table::
   :header-rows: 1
   :widths: 20 80

   * - Method
     - Description
   * - ``build()``
     - Generates the PyInstaller ``.spec`` file in ``.VIS/``
   * - ``release()``
     - Runs the full pipeline: build → PyInstaller → bundle → installer
   * - ``clean()``
     - Removes build artifacts and copies ``Icons``/``Images``/``.VIS`` into the dist folder
   * - ``newVersion()``
     - Increments the project version number in ``project.json``
