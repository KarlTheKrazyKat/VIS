Utilities
=========

fUtil
-----

``fUtil`` provides font creation and automatic text sizing. Import from ``VIStk``.

.. code-block:: python

    from VIStk import fUtil

``fUtil.mkfont(size, bold=False, font="default")``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Returns a font string compatible with Tkinter's ``font`` option. The default font is ``Arial``
on Windows and ``LiberationSans`` on Linux.

.. code-block:: python

    Label(parent, font=fUtil.mkfont(10))
    Label(parent, font=fUtil.mkfont(14, bold=True))

``fUtil.autosize(event, relations=None, offset=None, shrink=0)``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Automatically adjusts font size so the text fills the widget as tightly as possible. Bind to
``<Configure>`` on the widget to keep the font size updated as the widget resizes.

.. code-block:: python

    btn = Button(parent, text="Click Me", font=fUtil.mkfont(12))
    btn.bind("<Configure>", lambda e: fUtil.autosize(e))

.. list-table::
   :header-rows: 1
   :widths: 20 80

   * - Parameter
     - Description
   * - ``event``
     - The ``<Configure>`` event — provides the widget reference
   * - ``relations``
     - A list of additional widgets to resize to the same font size
   * - ``offset``
     - Integer subtracted from the calculated font size
   * - ``shrink``
     - Pixel margin subtracted from the widget width before calculating

**With relations (uniform button group):**

.. code-block:: python

    btns = [Button(parent, text=t, font=fUtil.mkfont(12)) for t in ["First","Prev","Next","Last"]]
    btns[0].bind("<Configure>", lambda e: fUtil.autosize(e, relations=btns[1:]))

Templates and the #% System
----------------------------

VIStk templates use ``#%`` comment markers as searchable section headers. The ``stitch`` command
uses these markers to locate and rewrite specific blocks in a screen script.

.. warning::

   Do not delete or rename ``#%`` comment lines. They are not standard comments — they are
   structural anchors that VIStk searches for by text pattern.

The critical blocks are:

.. code-block:: python

    #%Screen Elements
    import Screens.MyScreen.f_header
    import Screens.MyScreen.f_body

    #%Screen Modules
    import modules.MyScreen.m_header
    import modules.MyScreen.m_body

``stitch`` replaces the content under ``#%Screen Elements`` with fully-qualified imports for
each ``Screens/<screen>/f_*.py`` file, and ``#%Screen Modules`` with fully-qualified imports
for each ``modules/<screen>/m_*.py`` file. It also populates ``#%Build Screen Elements``
(inside ``setup()``) and ``#%Predefined Loop Functions`` (inside ``loop()``).

If the VSCode VIStk extension is installed, ``#%`` lines are highlighted differently from
regular comments.

Screen template structure
~~~~~~~~~~~~~~~~~~~~~~~~~

The full generated screen template:

.. code-block:: python

    #%Default Imports
    from Screens.defaults import *
    #%File Specific Imports

    #%Screen Modules

    #%Screen Elements

    #%Define Loop Modules
    def loop():
        """Called every tick by the Host (or standalone main loop)."""
        #%Predefined Loop Functions
        pass

        #%User Defined Loop Functions
        pass

    #%Menu Functions

    #%Host Hooks
    def configure_menu(menubar):
        """Register menu items with the containing TabManager."""
        menubar.set_screen_items([], label="ScreenName")

    def on_activate():
        """Called when this tab gains focus."""
        pass

    def on_deactivate():
        """Called when this tab loses focus."""
        pass

    def on_quit() -> bool:
        """Called when this screen is about to be destroyed.
        Return False to prevent destruction (e.g. unsaved changes prompt)."""
        pass

    def setup(parent):
        """Build this screen's UI into parent."""
        pane = LayoutFrame(parent)
        pane.place(relx=0, rely=0, relwidth=1, relheight=1)

        #%Screen Grid
        pane.Layout.colSize([1.0])
        pane.Layout.rowSize([1.0])

        #%Build Screen Elements

        #%Other Setup

    #%Standalone Entry
    if __name__ == "__main__":
        from Screens.root import root, frame
        setup(frame)
        root.Active = True
        root.WindowGeometry.setGeometry(width=66, height=66, align="center", size_style="screen_relative")
        root.screenTitle("ScreenName")
        root.setIcon("ScreenName")

        while True:
            try:
                if root.Active:
                    try:
                        loop()
                    except Exception as _e:
                        print(f"ScreenName loop error: {_e}", file=sys.stderr)
                    root.update()
                else:
                    break
            except Exception as _e:
                print(f"ScreenName main loop error: {_e}", file=sys.stderr)
                break

``Screens/defaults.py``
~~~~~~~~~~~~~~~~~~~~~~~~

Every project includes a ``Screens/defaults.py`` that centralizes the default imports
shared by all screen scripts and element files:

.. code-block:: python

    from tkinter import *
    from tkinter import ttk
    import sys
    from VIStk.Structures._Project import Project
    from VIStk.Widgets import LayoutFrame

    __all__ = [
        *[name for name in dir() if not name.startswith('_')],
    ]

``from Screens.defaults import *`` re-exports all names through ``__all__``, making them
available in the importing module. Static analysis tools (Pylance) and the Nuitka compiler
both resolve ``import *`` chains correctly.

Warnings
--------

Do not call ``root.mainloop()``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Using ``mainloop()`` traps the application in Tkinter's event loop and prevents the
``while root.Active`` pattern from working. Screen switching via ``os.execl`` cannot occur
from inside ``mainloop()``.

Do not call ``root.destroy()`` to quit
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Call ``root.Active = False`` instead. The ``while`` loop will exit naturally. Calling
``destroy()`` directly can leave VIStk in an inconsistent state if any exit actions or
redirects are queued.

Do not edit ``#%`` lines
~~~~~~~~~~~~~~~~~~~~~~~~~

The ``stitch`` command and VSCode extension locate blocks by searching for these exact strings.
Modifying them will break the CLI's ability to update your screen scripts automatically.
