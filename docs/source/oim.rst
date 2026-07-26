Outside Installable Media (OIM)
===============================

OIM lets a project ship **non-VIStk installable media** --- anything the VIStk build
pipeline cannot produce itself, such as a COM-registered C# add-in, an MSI, or a driver
--- *inside the same installer*, surfaced as an opt-in install choice backed by a
developer-supplied post-extract script.

Without OIM the only way to deliver such a payload is a second installer that the user
has to find and run separately, with no shared install location, no shared uninstall, and
no way to point the payload at the app's real runtime paths. OIM closes that gap.

OIM is a pure **folder convention**, discovered the same way ``commands/`` is. Nothing is
registered in ``project.json``.

.. contents:: On this page
   :local:
   :depth: 2

----

Folder layout
-------------

OIM lives at the project root. ``VINFO`` exposes it as ``p_oim``.

.. code-block:: text

   MyProject/
   └── OIM/
       └── <Name>/
           ├── manifest.json        <- optional metadata (see below)
           ├── media/               <- the payload (staged, then your script installs it)
           ├── icon/<image>         <- checkbox icon shown in the installer
           └── script/
               ├── install.py       <- optional; runs after media extraction
               └── uninstall.py     <- optional; runs on a full uninstall

Every subfolder of ``OIM/`` becomes one installable entry, named after the folder. Each
part is optional: an entry with only ``media/`` is extracted and left in place, and an
entry with only ``script/install.py`` is a pure side-effect hook.

The image under ``icon/`` is resized to 16x16 for the installer checkbox; if it is missing
or unreadable, the project icon is used instead.

manifest.json
~~~~~~~~~~~~~

``manifest.json`` is optional, as is every key in it.

.. code-block:: json

   {
     "label": "SolidWOM Add-in",
     "description": "WOM integration for SolidWorks",
     "default": false,
     "required": false
   }

.. list-table::
   :header-rows: 1
   :widths: 18 12 70

   * - Key
     - Default
     - Description
   * - ``label``
     - folder name
     - Display name on the installer's **Additional Software** row.
   * - ``description``
     - ``""``
     - Appended after the label, separated by an em dash.
   * - ``default``
     - ``false``
     - Whether the checkbox starts checked. Defaults off so OIM never silently
       bloats an install.
   * - ``required``
     - ``false``
     - Always installed; the row renders checked and disabled, and is excluded
       from the master **All** toggle so *All* can still reach fully-off.

A malformed ``manifest.json`` is ignored rather than fatal --- the entry falls back to
every default above.

----

How it ships and installs
-------------------------

Release
~~~~~~~

``Release.clean()`` copies ``OIM/`` to the **install root** of the build, not into
``runtime/``. It therefore rides into ``binaries.zip`` but stays out of the host-selected
``runtime/`` catch-all, so nothing is auto-installed. The release prints the entries it
bundled.

Selection
~~~~~~~~~

The installer discovers each ``OIM/<name>/`` by scanning the archive it carries, and
renders it as a selectable row under an **Additional Software** header on the installables
page.

``--Quiet`` selection follows three rules:

- ``required`` entries are always installed.
- A bare ``--Quiet`` (no screens named) installs **all** media.
- Otherwise only entries named on the command line are installed. An OIM name passed to
  ``--Quiet`` survives group expansion untouched, so it can be listed alongside screens
  and groups.

Install
~~~~~~~

For each selected entry the installer:

1. Stages the entry's archive members into ``<install>/OIM/<name>/``.
2. Execs ``script/install.py``, which owns the actual install of the staged media.
3. On success, copies ``script/uninstall.py`` to ``runtime/.VIS/oim/<name>/uninstall.py``,
   records the entry in ``install_log.json``, and deletes the staged folder.

The ``OIM/`` staging root is removed once it is empty. On failure the staged folder is
**left in place for diagnosis**, no record is written, the traceback goes to
``vis_installer.log``, and the failure is surfaced in the installer's status line --- but
a failing script never rolls back the already-committed app install.

Records land in the ``"oim"`` array of ``runtime/.VIS/install_log.json``:

.. code-block:: json

   {
     "oim": [
       {
         "name": "SolidWOM",
         "label": "SolidWOM Add-in",
         "uninstall_script": "runtime/.VIS/oim/SolidWOM/uninstall.py",
         "install_date": "2026-01-14T09:22:07"
       }
     ]
   }

Records are merged by ``name`` on a repair or update, so re-running the installer without
an entry selected does not drop its existing uninstall hook.

Uninstall
~~~~~~~~~

On a **full** uninstall the Uninstaller execs each recorded ``uninstall.py`` *before*
sweeping files, so media that registered state outside the install directory (COM/regasm,
the GAC, plugin folders) is cleaned up rather than orphaned. A partial uninstall --- one
that removes only some screens --- does not run the hooks, since the media may still be in
use. Hook errors are reported but never abort the uninstall.

----

The script contract
-------------------

``install.py`` and ``uninstall.py`` run **in-process** in the installer's or uninstaller's
own interpreter. They are *not* run by a system Python --- a clean target machine may not
have one, and the frozen installer's ``sys.executable`` is the installer itself. That has
four practical consequences:

- **Idempotent.** The script re-runs on every install and repair; OIM is staged fresh each
  time rather than persisted. Re-registering or re-stamping a config must be safe.
- **Stdlib subset.** Only modules bundled into the frozen installer are importable.
  ``os``, ``sys``, ``json``, ``subprocess``, ``pathlib``, and ``shutil`` are available ---
  the realistic pattern is to *shell out* (``regasm``, ``msiexec``) or to copy and stamp
  files. Avoid exotic stdlib modules (``sqlite3``, ``lzma``, ...) and all third-party
  imports.
- **Elevated.** The installer runs ``--uac-admin``, so the script inherits admin rights
  and RegAsm's HKLM write succeeds.
- **Quiet on failure.** ``--windowed`` swallows ``print``. Wrap risky work in
  ``try``/``except`` and report through ``log()``. Raising propagates as a failed entry.

Injected globals
~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 22 78

   * - Name
     - Meaning
   * - ``INSTALL_ROOT``
     - The install directory root.
   * - ``RUNTIME_DIR``
     - ``<INSTALL_ROOT>/runtime`` --- the app's ``python3xx.dll`` and shared
       ``.pyd`` files (e.g. ``pywomlib.pyd``).
   * - ``MEDIA_DIR``
     - ``<INSTALL_ROOT>/OIM/<name>/media``, the staged payload. **Install scripts
       only** --- the payload is gone by uninstall time.
   * - ``OIM_NAME``
     - This entry's folder name.
   * - ``APP_TITLE``
     - The project title.
   * - ``log(msg)``
     - Append a line to the installer log (``vis_installer.log``); in the
       uninstaller it writes to the uninstall console output.

Path stamping
~~~~~~~~~~~~~

The install location is chosen at install time, so a payload that needs to import from the
app --- a .NET add-in loading ``pywomlib.pyd``, for example --- cannot hard-code a path.
The install script is where that path is resolved: stamp ``RUNTIME_DIR`` into the
payload's own config before registering it.

.. code-block:: python

   import os, json, subprocess

   dll = os.path.join(MEDIA_DIR, "SolidWOM.AddIn.dll")

   # Stamp the add-in's config with this install's real runtime path.
   cfg = os.path.join(MEDIA_DIR, "solidwom.config.json")
   data = json.load(open(cfg))
   data["ExtraPaths"] = [RUNTIME_DIR]            # where pywomlib.pyd lives
   json.dump(data, open(cfg, "w"), indent=2)

   regasm = r"C:\Windows\Microsoft.NET\Framework64\v4.0.30319\RegAsm.exe"
   rc = subprocess.call([regasm, "/codebase", dll])
   log(f"regasm returned {rc}")
   if rc != 0:
       raise RuntimeError("RegAsm registration failed")   # keeps the entry staged for diagnosis

Note that ``regasm /codebase`` records the DLL's current location, so this script must
copy the payload somewhere permanent before registering it if ``MEDIA_DIR`` is not the
final home --- the staged folder is deleted once the script returns successfully.

The matching ``script/uninstall.py`` runs ``RegAsm /u`` on the same DLL, locating it from
``INSTALL_ROOT`` or ``RUNTIME_DIR`` since ``MEDIA_DIR`` is not injected there.
