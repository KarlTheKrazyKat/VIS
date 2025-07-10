# Changelog and Roadmap

## Changelog

0.3.1

- Added release command to release version of project

0.3.2

- Using internal project.json to build spec file to create release

0.3.3

- Adding a screen will add it to the json via a series of prompts

0.3.4

- Changed icons to relative path

0.3.5:

- Removed unecessary delete attempt that failed every time

0.3.6

- Added ```VIS remove sync``` to sync alpha beta and current

0.3.7

- VIS now uses mostly project.py to manage everything
- - this is much sleaker and faster
- - aiming to remove the need to use any subprocess.call

0.3.8

- releasing now uses the project.py modules and its classes
- project now stores default icon as an attribute
- no longer any subprocess.call()s anywhere but releasing
- releaseing now feature version metadata
- autoincreases the version on release current
- descriptions of screens now taken on creation

## Upcoming

0.3.9

- version numbering for screens control
- Auto title screens on creation
- Auto add icon to screen on creation
- Edit screen settings

### Pre Official Release

0.3.X:

- Auto title screens on creation
- Auto add icon to screen on creation
- Edit screen settings

0.4.X

- Modify default imports
- Set default screen size
- Set specific screen size
- Screen minsize option
- Screen open location options
- Open fullscreen (maybe)

0.5.X

- Create _module() function by default on element creation
- Enable/Disable Navigation
- More Navigation tools

0.6.X

- Update tools to ensure that updating VIS will not break code
- Rework code to make simpler
- Yes/No handler for prompts
- More robust project.py
- Consider where project name is stored

0.7.X

- Create VIS project in new folder
- Default .gitignore for VIS projects
- Repair broken screens to use templates
- Custom templates and template searching

0.8.X

- Expand custom frames
- Scrollable frame
- Scrollable menu
- More menu options

0.9.X

- Explore .EXE options
- - Using dlls?
- - Passing root rather than destroying root to launch new windows

1.0.0

- Explore tkinter styles
- - Setting screen styles
- - Creating global styles
- Sample VIS programs showing Icons, modules, Screens, menus

### Anytime

- Smart refresh screens (less root.updating)
- Windows Registry Stuff
- Show subscreens as subprocess in task manager
- Crash Logs
- Grid manager
- Tutorial?
- VIS GUI
- - GUI for VIS default settings
- - GUI for VIS project settings (defaults)
- - - GUI for VIS screens settings (name, icons, other)
- Auto updating of things like icon and script when changes are made

### Working with VIScode extension

- Configure auto object creation

#### Upcoming in vscode extension

- Add screen menu
- Add element menu
- Edit screen settings menu
- Global object format setting
- Global object format defaults
- Use local format for object creation if present
