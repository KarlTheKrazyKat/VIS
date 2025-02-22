Welcome to my Visual Interfacing Structure (VIS)!

Not much more than a framework for using tkinter right now 
Hopefully similar to Ruby on Rails.

Current capabilities include:
  add screen <screen> - creates a screen and prepares file structure
  add screen <screen> elements <element>-<element> - creates elements on screen (patches and stitches), modules, and creates screen if necessary
  new - initializes the current folder as a vis project
  patch <path> - replace default info in template with actual info
  stitch <screen> - links screen to elements and modules

Upcoming:
  screen info <screen> - reports back /Screens/<screen>/<screen>.txt
  screen info <screen> -N <info> - creates a new /Screens/<screen>/<screen>.txt with <info>
  screen info <screen> -E - opens /Screens/<screen>/<screen>.txt in vscode or notepad
  screen <screen> elements - reports all elements in /Screens/<screen> and if they are linked in <screen>.py
  screen <screen> modules - reports all modules in /modules/<screen> and if they are linked in <screen>.py

  project info - reports back /.VIS/description.txt
  project info -N <info> - creates a new /.VIS/description.txt with <info>
  project screens - reports all screens in project with <screen>.py and /Screens/<screen>
  project screens -D -reports all screens, elements, and modules as file structure with errors (i.e. unlinked) next to each file

  undo - will undo the last action taken by VIS (stored in .VIS/undo.txt)
