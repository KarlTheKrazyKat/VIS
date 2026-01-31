# Changelog and Roadmap

## Changelog

### 0.3 Releases

#### Changes

Releasing

- Added release command to release version of project
- Using internal project.json to build spec file to create release
- Can switch from Screen to Screen using internal methods (os)
- Can release single Screen
- Releasing creates Installers for the project

Screen Functionality

- Default Form Changed
- Currently active Screen is tracked

#### Widgets

New

- Window
- Root Widget (Tk, Window)
- SubRoot Widget (TopLevel, Window)
- WindowGeometry
- LayoutFrame(ttk.Frame)
- QuestionWindow (SubRoot)

Updated

- Menu: buttons highlight on hover

## Upcoming

- Default form should be changed
- Should track FPS through variable
- Should store copyright info somewhere
- version numbering for screens control
- Layout should have padding aswell
- Layout should have maximum size/minimum size option
- LayoutFrame Widget should exist to make it easier to manage frames with Layouts

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

1.0.0 Full Release

- Explore tkinter styles
- - Setting screen styles
- - Creating global styles
- Sample VIS programs showing Icons, modules, Screens, menus

### Anytime

- Windows Registry Stuff
- Show subscreens as subprocess in task manager
- Crash Logs
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
