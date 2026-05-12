VIStk
=====

**A lightweight framework for building multi-screen Tkinter applications.**

VIStk provides window and layout management, a project/screen registry, reusable widgets,
a tabbed Host shell, and a CLI for scaffolding and releasing apps. Standard Tkinter widgets
and geometry managers work alongside VIStk objects without conflict.

.. code-block:: bash

   pip install VIStk

Quick example --- create a project and launch it:

.. code-block:: bash

   mkdir MyApp && cd MyApp
   VIS new
   VIS MyApp

.. note::

   VIStk is under active development (|version|). API details may change between minor
   versions. See :doc:`changelog/index` for the latest changes and :doc:`knownissues` for
   open issues.

.. toctree::
   :maxdepth: 2
   :caption: Getting Started

   quickstart

.. toctree::
   :maxdepth: 2
   :caption: User Guide

   overview
   cli

.. toctree::
   :maxdepth: 2
   :caption: API Reference

   objects
   widgets
   structures
   utilities

.. toctree::
   :maxdepth: 1
   :caption: Project

   changelog/index
   knownissues
