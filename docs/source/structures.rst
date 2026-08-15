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
   * - ``p_settings``
     - Path to ``.VIS/settings.json`` — the application settings file owned by
       :ref:`project-settings`
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
   * - ``p_oim``
     - Path to ``OIM/`` — Outside Installable Media. Each ``OIM/<name>/`` holds
       ``media/``, ``icon/``, an optional ``manifest.json``, and
       ``script/install.py`` / ``script/uninstall.py`` run by the installer and
       uninstaller. Bundled into ``binaries.zip`` by ``Release.clean()``.
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
   * - ``project.Settings``
     - ``ProjectSettings``
     - Application settings backed by ``.VIS/settings.json`` — see
       :ref:`project-settings`
   * - ``project.d_icon``
     - ``str``
     - Default icon name
   * - ``project.d_window_icon``
     - ``str / None``
     - Optional project-level window *title-bar* icon (Windows ``ICON_SMALL``),
       read from ``defaults.window_icon`` in ``project.json``. When set, every
       window's title-bar chrome shows this icon while the taskbar button keeps
       using ``d_icon`` (``ICON_BIG``). ``None`` (the default) means the title
       bar shares the taskbar image, preserving prior behaviour. This is the
       only project-level way to set the window-chrome icon.
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
   * - ``load(screen, *args)``
     - ``None``
     - Calls ``Screen.load(*args)`` for the named screen
   * - ``open(screen, target=None, args=None)``
     - ``None``
     - Unified navigation — routes through the Host if one is running (deferred via the
       active TabManager's action queue), else falls back to ``Screen.load()``
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

``open(screen, target=None, args=None)``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Preferred navigation method when a Host may be running. Routing rules:

- **Host running + target is tabbed** — opens a new tab in the active TabManager's window.
  A single-instance tab is focused instead of duplicated.
- **Host running + target is standalone** — opens a new chromeless ``DetachedWindow`` in
  the same Host process.
- **No Host** — falls back to ``Screen.load()``, which spawns a Host subprocess (a no-op
  in a compiled build, where the exe *is* the Host).

When a Host is active the call is deferred through the active TabManager's action queue so
it runs safely from the main loop; pass ``target`` to use a specific TabManager's queue. To
*replace* the current pane instead of opening a new tab, call ``tab_manager.navigate(screen)``
directly.

.. code-block:: python

    # Prefer open() over load() for portable navigation
    root.Project.open("WorkOrders")
    root.Project.open("WorkOrders", args=["--won", "21930"])

.. _project-settings:

ProjectSettings
---------------

``ProjectSettings`` holds per-project application settings (0.6.0), persisted to
``.VIS/settings.json`` — the path exposed as ``VINFO.p_settings``. You never construct it;
it is attached to every ``Project`` as ``project.Settings``.

Settings are flat ``key -> value`` pairs. The dotted keys (``"window.min_width"``,
``"appearance.font_family"``) are a grouping convention only — they are treated as opaque
strings, so an app can store its own keys in any namespace it likes.

Unlike ``project.json``, which is shared with screens and groups, ``settings.json`` is wholly
owned by this object.

.. code-block:: python

    from VIStk.Structures import Project

    settings = Project().Settings

    settings.get("notifications.duration_ms")     # 5000 — framework default
    settings.get("my.custom.key", "fallback")     # explicit per-call default
    settings.set("appearance.font_family", "Consolas")
    settings.save()                               # persist to .VIS/settings.json

**Methods:**

.. list-table::
   :header-rows: 1
   :widths: 30 15 55

   * - Member
     - Returns
     - Description
   * - ``get(key, default)``
     - value
     - Resolution order: stored override → explicit ``default`` argument (when given) →
       framework ``DEFAULTS`` → ``None``.
   * - ``set(key, value)``
     - ``None``
     - Sets the override in memory. Call ``save()`` to persist.
   * - ``save()``
     - ``bool``
     - Writes the full resolved set (``effective()``) to ``.VIS/settings.json`` and clears
       ``dirty``. Returns ``False`` and warns to stderr if the file cannot be written — a
       failed save never crashes shutdown.
   * - ``effective()``
     - ``dict``
     - The full resolved map (``DEFAULTS`` merged with overrides). Used by the Settings UI,
       which needs a current value for every known key.
   * - ``reset(key)``
     - ``None``
     - Drops the override for ``key`` so it resolves back to its default.
   * - ``ensure_file()``
     - ``bool``
     - Materialises a default ``settings.json`` if none exists. Idempotent — an existing
       file (including hand edits) is never overwritten — and does not mark the store dirty.
       Returns ``True`` when a file was created. Never raises.
   * - ``key in settings``
     - ``bool``
     - ``True`` only when the key is an explicit override, not when it merely has a default.
   * - ``dirty``
     - ``bool``
     - ``True`` once an override has actually changed since the last ``save()``.
   * - ``DEFAULTS``
     - ``dict``
     - Class-level table of framework defaults for every known key (see below).

File lifecycle
~~~~~~~~~~~~~~

A full default ``settings.json`` — every key at its default value — is generated at
``VIS new`` scaffolding and on the first Host launch via ``ensure_file()``, so every
available option is visible and hand-editable rather than hidden behind an empty file.

In memory only genuine *overrides* are tracked: values that differ from ``DEFAULTS``, plus
any unknown custom keys. That is what makes ``reset()`` and ``in`` mean "explicitly
customised" even though the file on disk is complete. ``save()`` then writes the complete
resolved set back, keeping the file whole.

A missing file is normal (no overrides yet). A corrupt or unreadable file is non-fatal: the
failure is warned to stderr and the store falls back to defaults so the app still launches.

All ``DEFAULTS`` values are immutable (``None`` / ``bool`` / ``int`` / ``str``) because
``get()`` and ``effective()`` hand the default object back by reference — a mutable default
could be mutated in place by one caller and corrupt every later read. Represent an "empty
list" default as ``None`` and let callers coalesce with ``or []``.

The Host saves settings automatically on shutdown, on both the ``quit_host`` and
last-window-close paths, and only when ``dirty`` — so an app that touched no settings never
bumps the file's mtime. The session capture (``host.last_tabs``, ``window.last_geometry``)
is taken while the windows are still open but commits **only after** every window has closed
without veto, so a vetoed quit leaves settings untouched. Any other caller must invoke
``save()`` itself.

Built-in settings
~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 35 15 50

   * - Key
     - Default
     - Meaning
   * - ``window.default_width`` / ``window.default_height``
     - ``None``
     - First-window size. ``None`` falls back to 1200×800.
   * - ``window.default_align``
     - ``None``
     - Placement of the first window: ``"center"`` or a compass direction. ``None`` is
       treated as ``"center"``.
   * - ``window.min_width`` / ``window.min_height``
     - ``None``
     - Minimum window size; ``None`` imposes no minimum.
   * - ``window.remember_geometry``
     - ``False``
     - Restore the primary window's last size and position.
   * - ``window.fullscreen_on_launch``
     - ``False``
     - Open the first window maximized.
   * - ``window.last_geometry``
     - ``None``
     - Framework-written. Last primary-window geometry as ``"WxH+X+Y"``.
   * - ``host.start_with_os``
     - ``False``
     - Launch the Host at login (Windows).
   * - ``host.remember_tabs``
     - ``False``
     - Reopen the previous session's screens as tabs.
   * - ``host.last_tabs``
     - ``None``
     - Framework-written. List of tab base names from the last session.
   * - ``appearance.font_family``
     - ``None``
     - Default font family, applied to Tk's named fonts at launch. ``None`` keeps the
       platform default.
   * - ``appearance.font_size``
     - ``None``
     - Default font size, applied at launch. ``None`` keeps the widget default.
   * - ``appearance.color_scheme``
     - ``"system"``
     - Stored placeholder for the styles system; no effect yet.
   * - ``notifications.enabled``
     - ``True``
     - Global notification toggle.
   * - ``notifications.duration_ms``
     - ``5000``
     - Default banner/notification duration in milliseconds.

Appearance settings are applied once at launch — live re-styling of already-open windows is
deferred.

Keys absent from ``DEFAULTS`` are unknown to the framework and resolve to ``None`` (or the
caller's explicit default), which is what lets an app store its own settings here without
registering them.

The framework surfaces these keys in a built-in Settings window reached from the
**Settings** entry on every window's ``HostMenu``; apps contribute their own tabs with
``host.register_settings_panel(name, setup_fn)``. Both are documented alongside the widget
and the ``Host`` object.

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
   * - ``screen.window_icon``
     - ``str / None``
     - Optional window *title-bar* icon for this screen. Only honored when the
       screen owns a *standalone* (chromeless) window — a tabbed screen shares a
       chromed window that may host other screens, so its ``window_icon`` is
       ignored by design and that window uses the project-level
       ``d_window_icon``.
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
     - Loads this screen. Routes through the Host if one is running in-process; otherwise
       spawns a Host subprocess (skipped in a compiled build).
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
    rel.release()       # compile with Nuitka, bundle assets, create installer
    rel.restoreAll()    # undo any screen isolation

The release pipeline uses **Nuitka** for compilation (not PyInstaller). The installer and
uninstaller are built with PyInstaller and cached between releases.

.. _release-compiler:

Choosing the C compiler
~~~~~~~~~~~~~~~~~~~~~~~

Nuitka translates each module to C and then hands it to a real C compiler.
``release_info.compiler`` in ``project.json`` picks which one:

.. code-block:: json

   "release_info": {
       "location": "./dist/",
       "hidden_imports": [],
       "compiler": "clang"
   }

.. list-table::
   :header-rows: 1
   :widths: 15 20 65

   * - Platform
     - Accepted values
     - Notes
   * - Windows
     - ``msvc`` (default), ``clang``
     - ``msvc`` is always passed as ``--msvc=latest``. ``clang`` adds ``--clang``
       *on top* of it — Nuitka's Windows clang support is clang-cl piggy-backing on
       the Visual Studio installation, so MSVC remains a hard requirement.
   * - Linux
     - ``gcc`` (default), ``clang``
     - ``gcc`` needs no flag; ``clang`` maps to ``--clang``.
   * - macOS
     - ``clang`` (default)
     - The platform-native compiler; no flag needed.

Omitting the key (or leaving it empty) selects the platform default, which emits
exactly the flags the pipeline used before the key existed — existing projects
build identically.

MinGW64 gcc is deliberately **not** offered on Windows. It is a different C runtime
rather than just a different compiler, and Nuitka silently falling back to a
non-MSVC Windows toolchain is what produced the corrupt frozen-bytecode binaries
in #35.

``Release._check_compiler()`` validates the value before any compilation starts and
aborts with the accepted set on a typo or a platform mismatch. On Windows it locates
the Visual Studio installation with ``vswhere.exe`` (not ``$PATH`` — ``cl.exe`` is
only on ``PATH`` inside a Developer Command Prompt), and when ``clang`` is selected it
additionally requires ``clang-cl.exe`` under ``VC/Tools/Llvm``. That second check
matters because the pipeline passes ``--assume-yes-for-downloads``: without it, a
selected compiler Nuitka cannot find turns into a silent toolchain download.

.. note::

   ``clang-cl.exe`` comes from the **C++ Clang Compiler for Windows** individual
   component in the Visual Studio Installer. A VS install can already have a
   ``VC/Tools/Llvm`` directory holding only ``clang-format.exe`` /
   ``clang-tidy.exe`` — those ship with unrelated components and are not a compiler,
   which is why the check probes for ``clang-cl.exe`` by name.

.. warning::

   The component has to be installed in **the Visual Studio installation Nuitka
   selects**, which is not necessarily the one you reach for. On a machine with
   several installations, ``_list_msvc()`` ranks them the way SCons (and therefore
   ``--msvc=latest``) does: highest version first, then Enterprise > Professional >
   Community > BuildTools on a version tie.

   So a machine carrying both a Community and a BuildTools 2022 install at the same
   version compiles with **Community**, even though ``vswhere`` lists BuildTools
   first. Installing clang into BuildTools alone leaves the build failing in the
   Scons backend with ``Visual Studio has no Clang component found at ...``. Run
   ``VIS release`` (or the pre-flight directly) to see which installation is
   selected and whether it has clang-cl:

   .. code-block:: python

      from VIStk.Structures._Release import Release
      for version, product, path in Release._list_msvc():
          print(product, version, bool(Release._find_clang_cl(path)), path)
      print("selected:", Release._find_msvc())

   ``$PATH`` is deliberately not consulted — Nuitka derives the clang directory from
   wherever ``cl.exe`` resolved, so a standalone LLVM on ``PATH`` would be a false pass.

Object files and Nuitka's compile cache are compiler-specific, so a **non-default**
compiler builds under its own root — ``build/<pendix>-<compiler>/`` instead of
``build/<pendix>/``. Switching between ``msvc`` and ``clang`` therefore keeps both
caches warm rather than forcing a cold rebuild each way. Deliverable paths
(``dist/<pendix>/``) are unaffected; the compiler is a build detail, not part of the
release name.

Compilation order
~~~~~~~~~~~~~~~~~

Compilations are grouped into three categories and executed in this order:

1. **Required Packages** — Shared libraries (e.g. ``pywomlib``, ``VIStk``) compiled as
   ``.pyd`` modules into ``shared/``.
2. **Screens** — Every tabbed screen compiled as a ``.pyd`` module into ``Screens/``.
   The default screen is included.
3. **Binaries** — Standalone screens (``tabbed=false, release=true``) compiled as ``.exe``
   files, plus the Host binary.

The Host is compiled last with ``--standalone --follow-imports`` and bundles the ``modules/``
and ``Screens/`` packages so that screen ``.pyd`` files can resolve their imports at runtime.

Progress is displayed on a single overwriting line:

.. code-block:: text

    PYWOM Release - 19 Compilations
      [5/19] Screens 3/14 - WOMServant — C 12/45

If any compilation fails, the release aborts immediately with a clear error message.
No ``.py`` source files are ever included in the release — if a ``.pyd`` compilation fails,
the release fails.

**Methods:**

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Method
     - Description
   * - ``release()``
     - Runs the full pipeline: version bump → Nuitka compilation → asset bundling →
       installer assembly. Warns if no default screen is set.
   * - ``compile_shared()``
     - Compiles top-level packages from ``hidden_imports`` as ``.pyd`` modules.
   * - ``compile_screens(mode)``
     - Compiles screens. ``mode="pyd"`` for tabbed, ``mode="exe"`` for standalone.
   * - ``compile_host()``
     - Compiles the Host as a standalone Nuitka executable.
   * - ``clean()``
     - Copies assets (Icons, Images, ``.VIS``) into the dist folder, rewrites
       ``project.json`` with ``.pyd`` script paths, and removes build artifacts.
   * - ``newVersion()``
     - Increments the project version number in ``project.json``.
