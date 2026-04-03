CLI Reference
=============

The ``VIS`` command is available after installing VIStk. All commands are case-insensitive
and accept single-letter abbreviations.

Initialize a project
--------------------

.. code-block:: text

   VIS new

Run from the folder where you want to create the project. Creates the ``.VIS/`` folder,
copies default templates, generates ``Host.py``, and prompts for:

- Project name
- Company name
- Copyright string (defaults to company name)
- Initial version
- Default screen name

Add a screen
------------

.. code-block:: text

   VIS add screen <screen_name>

Creates a new screen script from template, registers it in ``project.json``, and creates
the matching ``Screens/<screen>/`` and ``modules/<screen>/`` folders.

The CLI will prompt for:

- Script filename
- Whether the screen should have its own ``.exe`` (``release``)
- Icon name
- Description
- Whether the screen opens as a tab inside the Host (``tabbed``)
- Whether this screen is the default screen (prompted only if no default is set yet)

Add elements to a screen
------------------------

.. code-block:: text

   VIS add screen <screen_name> elements <element_name>
   VIS add screen <screen_name> elements <e1>-<e2>-<e3>

Creates ``f_<element>.py`` in ``Screens/<screen>/`` and a blank ``m_<element>.py`` in
``modules/<screen>/``, then runs ``stitch`` to wire them into the screen script. Multiple
elements can be created in one call by separating names with ``-``.

Add a menu module to a screen
------------------------------

.. code-block:: text

   VIS add screen <screen_name> menu <menu_name>

Creates ``modules/<screen>/m_<menu_name>.py`` pre-filled with a
``configure_menu(menubar)`` stub.

If ``modules/<screen>/m_<screen>.py`` (the hooks module) already exists:

- If it does **not** define ``configure_menu`` — a delegation function is appended
  automatically so the new menu module is called on tab focus.
- If it **already** defines ``configure_menu`` — import instructions are appended as
  comments for manual wiring.

Example:

.. code-block:: text

   VIS add screen WorkOrders menu FileMenu

Stitch a screen
---------------

.. code-block:: text

   VIS stitch <screen_name>

Scans ``Screens/<screen>/`` and ``modules/<screen>/`` for all ``f_*`` and ``m_*`` files
and rewrites the import blocks in the screen script to include them all. This is called
automatically when adding elements. Run manually if you add files without using the CLI.

Release the project
-------------------

.. code-block:: text

   VIS release -f <suffix> -t <type> -n <note>

Builds a PyInstaller spec for all screens marked ``release: true`` in ``project.json``,
compiles them to native binaries, bundles required assets (``Icons``, ``Images``,
``.VIS``), and creates a standalone installer executable. The binaries land in ``dist/``.

.. list-table::
   :header-rows: 1
   :widths: 20 15 65

   * - Flag
     - Short
     - Description
   * - ``-Flag``
     - ``-f``
     - Suffix appended to the output folder name
   * - ``-Type``
     - ``-t``
     - Version increment type: ``Major``, ``Minor``, or ``Patch``
   * - ``-Note``
     - ``-n``
     - Release note (informational)

Release a single screen
-----------------------

.. code-block:: text

   VIS release Screen <screen_name> -f <suffix>

Temporarily marks all other screens as non-releasing, builds only the named screen, then
restores the others.

Launch the Host
---------------

.. code-block:: text

   VIS <project_name>
   VIS <project_name> <screen_name>

Launches the Host for the current project, or brings an already-running Host to the
foreground. ``<project_name>`` must match the project title in ``project.json``
(case-sensitive).

- ``VIS <project_name>`` — starts the Host if not running, then opens the default screen.
- ``VIS <project_name> <screen_name>`` — starts the Host if not running, then opens the
  named screen.

Both forms start the Host as a subprocess and communicate via IPC. If the Host is already
running, only the IPC message is sent.

Example — if the project is named ``MyApp``:

.. code-block:: text

   VIS MyApp                  # open default screen
   VIS MyApp WorkOrders       # open a specific screen

Rename a screen
---------------

.. code-block:: text

   VIS rename <screen_name> <new_name>

Renames a screen throughout the project:

- Renames the key in ``project.json → Screens``
- Renames the script file if it follows the default convention; updates the ``script``
  field
- Renames ``Screens/<oldname>/`` → ``Screens/<newname>/``
- Renames ``modules/<oldname>/`` → ``modules/<newname>/`` and renames
  ``m_<oldname>.py`` → ``m_<newname>.py``
- Rewrites all ``Screens.<oldname>.`` and ``modules.<oldname>.`` import references in
  the screen script
- Updates ``default_screen`` in ``project.json`` if it points to the old name
- Runs ``stitch`` automatically so import blocks are regenerated

Edit a screen attribute
-----------------------

.. code-block:: text

   VIS edit <screen_name> <attribute> <value>

Directly sets any attribute in a screen's ``project.json`` entry.

.. list-table::
   :header-rows: 1
   :widths: 25 15 60

   * - Attribute
     - Type
     - Notes
   * - ``script``
     - string
     - Must point to an existing ``.py`` file in the project root
   * - ``release``
     - bool
     - ``true``/``yes``/``1`` or ``false``/``no``/``0``
   * - ``icon``
     - string / none
     - ``none`` or ``null`` clears the icon
   * - ``desc``
     - string
     - Free-form description
   * - ``tabbed``
     - bool
     - Whether this screen opens as a Host tab
   * - ``single_instance``
     - bool
     - When ``true``, re-opening focuses the existing instance
   * - ``version``
     - string
     - Must be ``major.minor.patch`` format
   * - ``current``
     - string / none
     - ``none`` or ``null`` clears the value

Examples:

.. code-block:: text

   VIS edit WorkOrders single_instance true
   VIS edit Dashboard tabbed false
   VIS edit Settings version 2.0.0

Stop the Host
-------------

.. code-block:: text

   VIS stop

Sends a quit signal to the running Host via IPC. The Host shuts down gracefully. Prints a
message if no Host is running.

Check version
-------------

.. code-block:: text

   VIS -v

Prints the installed VIStk version.
