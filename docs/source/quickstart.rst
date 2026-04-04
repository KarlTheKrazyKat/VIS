Quickstart
==========

This guide walks you through installing VIStk, creating a project, building screens,
and shipping a release. Each step builds on the previous one.

1. Install VIStk
-----------------

.. code-block:: bash

   pip install VIStk

Verify the installation:

.. code-block:: bash

   VIS -v

This prints the installed version number. If ``VIS`` is not found, make sure your
Python ``Scripts/`` directory is on your ``PATH``.

2. Create a project
--------------------

Create a folder for your app and run ``VIS new`` inside it:

.. code-block:: bash

   mkdir MyApp
   cd MyApp
   VIS new

The CLI prompts for:

- **Project name** --- defaults to the folder name
- **Company name**
- **Copyright string** --- defaults to the company name
- **Initial version** --- e.g. ``0.1.0``
- **Default screen name** --- the first screen the app opens

This generates the ``.VIS/`` folder (project registry, templates, Host entry point) and
scaffolds your first screen.

Your project now looks like this:

.. code-block:: text

   MyApp/
   ├── .VIS/
   │   ├── project.json
   │   ├── Host.py
   │   └── Templates/
   ├── Screens/
   │   └── Home/
   ├── modules/
   │   └── Home/
   ├── Icons/
   ├── Images/
   └── Home.py

3. Understand the screen script
--------------------------------

Open the generated screen script (e.g. ``Home.py``). The important parts:

.. code-block:: python

   def setup(parent):
       """Build this screen's UI into parent."""
       from tkinter import ttk
       label = ttk.Label(parent, text="Hello from Home")
       label.pack(padx=20, pady=20)

   if __name__ == "__main__":
       from Screens.root import root, frame
       setup(frame)
       root.Active = True
       root.screenTitle("Home")

       while True:
           if root.Active:
               root.update()
           else:
               break

- ``setup(parent)`` is where all widget creation goes. The Host calls this function
  when loading the screen as a tab.
- The ``if __name__ == "__main__":`` block lets you run the screen standalone for
  testing.

4. Launch the app
------------------

Start the Host (the persistent tabbed shell):

.. code-block:: bash

   VIS MyApp

This opens the Host window and loads your default screen as a tab. The Host lives in
the system tray --- closing the window hides it rather than quitting. Use **App > Quit**
from the menu bar or ``VIS stop`` from the terminal to fully shut down.

You can also open a specific screen directly:

.. code-block:: bash

   VIS MyApp Home

Or run a screen standalone (no Host):

.. code-block:: bash

   python Home.py

5. Add more screens
--------------------

.. code-block:: bash

   VIS add screen Settings

The CLI prompts for script filename, icon, description, and whether the screen is
tabbed. After creation you get:

.. code-block:: text

   MyApp/
   ├── Screens/
   │   ├── Home/
   │   └── Settings/
   ├── modules/
   │   ├── Home/
   │   └── Settings/
   ├── Home.py
   └── Settings.py

Navigate between screens from code:

.. code-block:: python

   from VIStk.Structures._Project import Project
   Project().open("Settings")

6. Add UI elements to a screen
-------------------------------

Elements are modular UI sections. Each element gets an ``f_`` file (UI) in
``Screens/<screen>/`` and an ``m_`` file (logic) in ``modules/<screen>/``.

.. code-block:: bash

   VIS add screen Home elements header-body-footer

This creates ``f_header.py``, ``f_body.py``, ``f_footer.py`` and their matching
``m_`` files, then runs ``stitch`` to wire the imports into ``Home.py``.

Build your UI inside each element's ``build()`` function:

.. code-block:: python

   # Screens/Home/f_header.py
   from tkinter import ttk

   f_elem = None

   def build(parent):
       global f_elem
       f_elem = ttk.Frame(parent)
       f_elem.place(parent.Layout.cell(0, 0))
       ttk.Label(f_elem, text="Header").pack()

7. Use layouts
--------------

VIStk's ``Layout`` system divides frames into proportional rows and columns:

.. code-block:: python

   def setup(parent):
       from VIStk.Widgets import LayoutFrame

       pane = LayoutFrame(parent)
       pane.place(relx=0, rely=0, relwidth=1, relheight=1)
       pane.Layout.rowSize([0.1, 0.8, 0.1])    # header, body, footer
       pane.Layout.colSize([0.25, 0.75])         # sidebar, content

       sidebar = ttk.Frame(pane)
       sidebar.place(**pane.Layout.cell(1, 0))

       content = ttk.Frame(pane)
       content.place(**pane.Layout.cell(1, 1))

8. Add menus
------------

Contribute items to the Host menu bar from your screen:

.. code-block:: python

   def configure_menu(menubar):
       menubar.set_screen_items([
           {"label": "Refresh", "command": refresh},
           {"separator": True},
           {"label": "Export",  "command": export},
       ], label="Home")

The menu items appear when your tab is active and are automatically cleared when another
tab takes focus.

You can also scaffold a dedicated menu module:

.. code-block:: bash

   VIS add screen Home menu FileMenu

9. Release the app
-------------------

Build a distributable installer:

.. code-block:: bash

   VIS release -t Patch -n "First release"

This:

1. Increments the version number (``-t`` controls Major/Minor/Patch)
2. Generates a PyInstaller spec from ``project.json``
3. Compiles all screens marked ``release: true`` to native binaries
4. Bundles assets (Icons, Images, .VIS)
5. Creates a standalone installer executable in ``dist/``

Release a single screen instead of the full project:

.. code-block:: bash

   VIS release Screen Home

Next steps
----------

- :doc:`overview` --- project structure, app lifecycle, and the screen module pattern in
  detail
- :doc:`cli` --- full CLI reference for all ``VIS`` commands
- :doc:`objects` --- ``Root``, ``Host``, ``Layout``, and other core objects
- :doc:`widgets` --- ``TabBar``, ``HostMenu``, ``ScrollableFrame``, and more
- :doc:`structures` --- ``Project``, ``Screen``, ``Version``, ``Release``
- :doc:`changelog/index` --- release history and roadmap
