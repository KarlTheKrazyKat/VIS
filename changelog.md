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

0.3.9

- releaseing now features version metadata
- autoincreases the version on release current
- descriptions of screens now taken on creation

0.3.10

- just messed up the version number

0.3.11

- new wrapper class for root
- new wrapper class for toplevel
- new window geometry class to control window sizing easily
- new menu window widget

0.3.12 Adding more Widgets!!

- highlight menu buttons on hover

0.3.12.1

- fix default color after menu button unhighlight

0.3.12.2

- new widget question window (dropdown list not accessable yet)

0.3.12.3

- lowered required python version

0.3.12.4

- trying a fix for linux version

0.3.12.17

- fixed an error on VIS project setup

0.3.12.18

- screen switching slightly functional
- changed method of mainloop replacement

0.3.12.19

- Updated form.zip
- changed from regular comments to `#%` pattern
- - works in tandem with VIS extension to make VIS headers stand out

0.3.13

- Screen load now uses `os.execl` to replace current process with one running the new screen

## Upcoming

0.3.13.15

- Create binary for single screen
- auto screen/icon might exist alredy?

### Pre Official Release

0.3.X: Releases

- version numbering for screens control
- Auto title screens on creation
- Auto add icon to screen on creation

0.4.X Application Settings

- Edit screen settings
- Set default screen size
- Set specific screen size
- Screen minsize option
- Screen open location options
- Open fullscreen (maybe)

0.5.X Defaults

- Modify default imports
- Default templates

0.6.X Keyboard Navigation

- Enable/Disable Navigation
- More Navigation tools

0.7.X Updating Tools

- Update tools to ensure that updating VIS will not break code
- Tools to update created binaries

0.8.X Advanced Creation and Restoration

- Create VIS project in new folder
- Default .gitignore for VIS projects
- Repair broken screens to use templates

0.9.X Vis Widgets

- Expand custom frames
- Scrollable frame
- Scrollable menu
- More menu options

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
