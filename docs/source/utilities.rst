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

The two critical blocks are:

.. code-block:: python

    #%Screen Elements
    from Screens.myscreen.f_header import *
    from Screens.myscreen.f_body import *
    #%Screen Grid

    #%Screen Modules
    from modules.myscreen.m_header import *
    from modules.myscreen.m_body import *
    #%Handle Arguments

``stitch`` replaces everything between ``#%Screen Elements`` and ``#%Screen Grid`` with fresh
imports from ``Screens/<screen>/f_*.py``, and everything between ``#%Screen Modules`` and
``#%Handle Arguments`` with fresh imports from ``modules/<screen>/m_*.py``.

If the VSCode VIStk extension is installed, ``#%`` lines are highlighted differently from
regular comments.

Screen template structure (0.4+)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The full generated screen template:

.. code-block:: python

    #%Default Imports
    from tkinter import *
    from tkinter import ttk
    import sys
    #%File Specific Imports

    #%Handle Arguments

    #%Screen Modules

    #%Define Loop Modules
    def loop():
        pass

    def configure_menu(menubar):
        """Contribute menu items to the Host's persistent menu bar."""
        pass

    def on_focused():
        """Called when this tab gains focus inside the Host."""
        pass

    def on_unfocused():
        """Called when this tab loses focus or is closed inside the Host."""
        pass

    def setup(parent):
        """Build this screen's UI into parent."""
        #%Screen Grid

        #%Screen Elements
    #%Update Loop
    if __name__ == "__main__":
        from Screens.root import root, frame
        setup(frame)
        root.Active = True
        root.WindowGeometry.setGeometry(width=66, height=66, align="center", size_style="screen_relative")
        root.screenTitle("<title>")
        root.setIcon("<icon>")

        while True:
            try:
                if root.Active:
                    try: loop()
                    except: pass
                    root.update()
                else:
                    break
            except:
                break

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
