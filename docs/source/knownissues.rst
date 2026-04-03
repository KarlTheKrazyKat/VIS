Known Issues
============

Unresolved
----------

Host / IPC
~~~~~~~~~~

Args passed to ``Project.load()`` are silently dropped over IPC
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

*Found in 0.4.2*

``Screen.load()`` sends only the screen name string over the IPC socket — extra args (e.g., ``--path``) are not transmitted. The Host listener opens a fresh blank tab with no knowledge of the args. Affects any screen that needs to receive a file path or flag via Host IPC.

**Known work-arounds:** None (architectural limitation until IPC layer is extended)

----

Resolved
--------

HostMenu
~~~~~~~~

Menubar cascades permanently deleted when tab label matches project layer label
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

*Found in 0.4.2 — Fixed in 0.4.2*

``clear_screen_items()`` now deletes by index (reverse order) instead of label string.

Form/Template
~~~~~~~~~~~~~

Relative path breaks after .exe is created
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

*Found 0.3.3 — Fixed 0.3.6*

Form Extracts Wrong
^^^^^^^^^^^^^^^^^^^

*Found 0.3.6 — Fixed 0.3.7*
