# Changelog and Roadmap

## Changelog

### 0.3 Release

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
- Can load with args

#### Objects

New

- VIMG can bind image path resizing to widget

#### Widgets

New

- Window
- Root Widget (Tk, Window)
- SubRoot Widget (TopLevel, Window)
- WindowGeometry
- LayoutFrame (ttk.Frame)
- QuestionWindow (SubRoot)
- ScrollableFrame (ttk.Frame)
- ScrollMenu (ScrollableFrame)

Updated

- Menu: buttons highlight on hover
-     : can provide screennames instead of paths
- MenuItem(Button): now menuitem is the button and text autosizes
-                 : will use screen.load() if provided with screenname

---

### 0.4.X Host and Tabbed Screens

#### Completed

**Host object**

- `Host` — persistent `Root` subclass; hides to system tray on window close; never destroys
- Host registers itself in the Windows startup registry on first run (`_register_startup`)
- Host is always the parent process and sole owner of the Tk root window
- Closing the Host window hides it to tray; `VIS stop` or tray Quit fully shuts it down
- Thread-safe cross-thread call queue (`queue.SimpleQueue`) polled by `_poll_main_queue`; pystray and IPC threads never call Tkinter directly
- `_HOST_INSTANCE` module-level singleton; `Project.open()` checks it to route navigation

**TabManager and TabBar**

- `TabManager` object — `Frame` subclass that owns the tab strip and content area; sits at the top level of the Host window
- `TabBar` widget — row of clickable tabs; flat buttons with configurable background colours; active/inactive/hover states; close button per tab; vertical separator between tabs
- Tab buttons show the screen icon (16×16 PIL image) to the left of the screen name when an icon is configured
- Full hover behaviour: hovering the tab name button changes both the name and close button together; hovering the close button alone changes only the close button to IndianRed

**Screen navigation**

- `host.open(screen)` — unified navigation; tabbed screens open as Frame tabs inside Host window; standalone screens open as `Toplevel` windows within the Host process
- `TabManager.open_tab` / `TabManager.close_tab` — full tab lifecycle including `setup()`, `on_activate()`, `on_deactivate()` hooks
- `__VIS_CLOSE__:<name>` IPC message — a screen can ask the Host to close itself

**IPC**

- `send_to_host(project_title, message)` — sends any message to a running Host via localhost TCP
- Host writes its port to `%TEMP%/<ProjectTitle>_vis_host.port` on startup; removed on quit
- IPC messages: screen name (open), `__VIS_QUIT__` (shut down), `__VIS_CLOSE__:<name>` (close one screen)

**Screen hooks**

- `setup(parent)` — called with the tab Frame when the Host opens a screen as a tab; all widget creation must be inside this function so the module can be imported without side-effects
- `configure_menu(menubar)` — called when a tab activates; screen contributes items to `HostMenu`; items cleared on deactivation
- `on_activate()` / `on_deactivate()` — lifecycle hooks called on tab focus change

**Screen template**

- Hook stubs (`configure_menu`, `on_activate`, `on_deactivate`) placed before `setup()` so `stitch()` cannot overwrite them
- All widget creation sections (`#%Screen Grid`, `#%Screen Elements`) placed inside `setup(parent)` to avoid import side-effects
- Standalone entry point uses `if __name__ == "__main__":` guard; imports `root, frame` from `Screens/root.py` only in that block
- `_replace_section` regex fixed: `(?=\n?[ \t]*#%)` — the `\n` is now optional so adjacent `#%` markers (no blank line between) are handled correctly

**VIS commands**

- `VIS stop` — sends `__VIS_QUIT__` to a running Host via IPC
- `VIS <ProjectName>` — starts the Host if not running (via `subprocess.Popen`), then sends the default screen name via IPC so the window surfaces automatically
- `VIS <ProjectName> <ScreenName>` — starts the Host if not running, then sends the screen name via IPC; no longer falls back to `os.execl`
- `VIS new` — prompts for default screen name after project creation

**Project creation**

- Project name defaults to the current folder name (press Enter to accept)
- Project name is validated against reserved VIS commands (`new`, `add`, `stop`, `stitch`, `release`, `-v`, etc.)
- `VIS new` prompts for a default screen immediately after project creation
- `Host.py` generated into `.VIS/Host.py` instead of the project root (not intended for user editing)
- `default_screen` stored under `defaults.default_screen` in `project.json` (previously top-level); backwards-compatible read path retained

**Dependencies added**

- `pystray` — cross-platform system tray support

---

**Tab drag-to-reorder**

- Tabs in the TabBar can be dragged left or right to change their display order
- An 8-pixel motion threshold distinguishes a drag from a click
- The tab click action is suppressed when a drag occurred in the same press

**InfoRow widget**

- `InfoRow` widget — `Frame` packed at the bottom of the Host window
- Left: active screen name and version (updated on tab focus change)
- Centre: project copyright string (static, set at Host startup)
- Right: live frames-per-second counter (updated once per second by `tick_fps`)

**Host quit closes managed screens**

- `_do_quit()` now calls `on_deactivate` hooks and destroys all managed Toplevels and tabs before tearing down the Tk root

**Layout constraint enforcement**

- `Layout` now stores its parent frame reference in `__init__`
- New `Layout.apply(widget, row, col, ...)` method places a widget with absolute pixel coordinates and re-places it automatically on every parent `<Configure>` event, enforcing the `minsize` and `maxsize` constraints set via `rowSize()` / `colSize()`
- Existing `cell()` method is unchanged — relative-placement workflows are unaffected

#### Planned

- Rename `on_activate()` / `on_deactivate()` hooks to `on_focused()` / `on_unfocused()` for clarity
- Locate screen lifecycle hooks in `modules/<screen>/m_<screen>.py` rather than the screen script itself
- Tab right-click context menu — option to pop the tab out into its own window with its own TabManager
- Tab drag-to-detach — drag a tab out of the tab bar to open in its own window
- Tab drag-to-merge — drag a tab into another window's tab bar to move it there

---

### 0.5.X VIS Widgets

Widgets that Tkinter does not provide natively. General-purpose and usable in any VIStk app.

- `Tooltip` — hover tooltip bound to any widget; Tkinter has no native tooltip
- `CollapsibleFrame` — frame with a header button that toggles content visibility
- `AutocompleteEntry` — Entry with a filtered dropdown suggestion list
- `DateEntry` — date input widget with format validation and optional calendar picker popup
- Expand custom frames
- More menu options
- Color palette feature — recolor default VIStk widgets; accessible throughout user code

**Tab bar enhancements**

- Tab bar position — top, left, bottom, or right
- Maximum simultaneous open tabs — enforced when opening new tabs
- Close confirmation — warn when closing a tab with unsaved state (requires `has_unsaved()` hook)
- Stored tabs with a tab ID to allow multiple tabs of the same screen

---

### 0.6.X Application Settings

Settings stored per-project in `.VIS/settings.json`, accessed via `Project.settings`.

**Storage and API**

- `Project.settings.get(key, default)` — read a setting
- `Project.settings.set(key, value)` — write a setting
- `Project.settings.save()` — persist to `.VIS/settings.json`; called automatically on Host close

**Window and display**

- Default window size, alignment, and minimum size
- Remember last window size and position; restore on next open
- Open fullscreen on launch toggle

**Host and tray**

- Start Host with OS — toggle that enables/disables the startup registry entry
- Start minimized — Host starts hidden in tray rather than showing the window
- Remember open tabs — reopen the tabs that were open when the Host last closed

**Appearance**

- Default font family and size
- Color scheme selection — placeholder for styles system

**Notifications**

- Enable/disable toast notifications globally
- Toast display duration in milliseconds

**Settings UI**

- Built-in settings panel opens from HostMenu → Settings
- Settings panel is a tabbed interface — VIStk settings on one tab, developer's custom settings on additional tabs
- Developer registers a custom settings panel via `host.register_settings_panel(name, setup_fn)`
- Tray menu includes a Settings entry

---

### 0.7.X Defaults, Navigation, and Updating Tools

- Modify default imports
- Default templates
- Enable/Disable Keyboard Navigation
- More Navigation tools
- Update tools to ensure that updating VIS will not break code
- Tools to update created binaries

---

### 0.8.X Advanced Creation and Restoration

- Create VIS project in new folder
- Default `.gitignore` for VIS projects
- Repair broken screens to use templates

---

### 0.9.X Notifications

- `Toast` — non-blocking status overlay that auto-dismisses after a delay; respects the global notification enable/disable setting from 0.6.X

---

### 1.0.0 Full Release

- Explore tkinter styles
  - Setting screen styles
  - Creating global styles
- Sample VIS programs showing Icons, modules, Screens, menus

---

### Anytime

- Show subscreens as subprocess in task manager
- Crash Logs
- Tutorial
- VIS GUI
  - GUI for VIS default settings
  - GUI for VIS project settings (defaults, screens, icons)
- Auto updating of things like icon and script when changes are made

---

### Working with VIScode Extension

- Configure auto object creation

#### Upcoming in VSCode extension

- Add screen menu
- Add element menu
- Edit screen settings menu
- Global object format setting
- Global object format defaults
- Use local format for object creation if present
