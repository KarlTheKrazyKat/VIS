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

## Upcoming

General items not yet assigned to a milestone:

0.4.X Host and Tabbed Screens

The Host is the foundational new object for VIStk. It is a persistent background process that owns the application's Root window. It lives in the system tray when no UI is visible and never closes unless the user explicitly quits from the tray menu. All screen navigation routes through the Host when it is running. This milestone must come before all others because subsequent features (HostMenu, settings UI, styles, VIS GUI) all depend on it.

**Process model:**

- Host is always the parent process and sole owner of the Tk Root
- Tabbed screens are Frames within the Host window
- Standalone screens are subprocesses spawned by the Host (`subprocess.Popen`), never `os.execl` from the Host
- `os.execl` is only used in the fully standalone case (no Host running) — existing behavior is preserved

**Screen navigation routing (Host running):**

- Target is a tabbed screen → open or focus its tab in the Host window
- Target is standalone, caller wants to close → Host spawns subprocess, caller closes
- Target is standalone, caller wants to stay open → Host spawns subprocess in its own window

**What gets built:**

- `Host` object — persistent `Root` subclass; hides to system tray on window close; never destroys; registers to OS startup on first run
- `TabBar` widget — row of clickable tabs at the top of the Host window; supports opening, closing, and focusing tabs
- `HostMenu` widget — persistent Tkinter Menu on the Host; has base items always present and screen-contributed items that swap when the active tab changes
- `host.open(screen)` — unified navigation function; routes to tab, subprocess, or `os.execl` based on Host presence and screen `tabbed` setting
- Screen `tabbed` property — added to `project.json` per screen; `VIS add screen` gains a prompt for this; developer-controlled
- Screen `setup(parent)` hook — called when a tab is first opened; builds the screen UI into the provided Frame; must be defined for a screen to support tabbing
- Screen `configure_menu(menubar)` hook — called when a tab activates; screen contributes its menu items to `HostMenu`; cleared when tab deactivates
- Screen `on_activate()` / `on_deactivate()` lifecycle hooks — called on tab focus change; use for resuming/pausing timers, refreshing data
- System tray integration — tray icon always present when Host is running; click restores window; tray menu includes Quit
- OS startup registration — Host registers itself in the OS startup mechanism on first run (Windows registry); can be toggled in settings
- Updated screen template — adds `setup()`, `configure_menu()`, `on_activate()`, `on_deactivate()` stubs and `__main__` guard for standalone compatibility
- FPS tracking — Host tracks frames-per-second through a variable accessible to all screens
- Screen version numbering — per-screen version number stored in `project.json` and accessible via `screen.s_version`
- Copyright storage — project copyright info stored in `project.json` and accessible via `project.copyright`
- `Layout` padding — padding parameter added to `Layout` cells
- `Layout` size constraints — minimum and maximum size options for `Layout` rows and columns

**New dependency:** `pystray` for cross-platform system tray support

0.5.X Vis Widgets

Widgets that Tkinter does not provide natively. These are general-purpose and usable in any VIStk app. Moved up because several (Tooltip, CollapsibleFrame) are directly useful in the Host and settings UI built in subsequent milestones.

- `Tooltip` — hover tooltip bound to any widget; binds/unbinds on `<Enter>`/`<Leave>`; Tkinter has no native tooltip
- `CollapsibleFrame` — frame with a header button that toggles content visibility; Tkinter has no native collapsible section
- `AutocompleteEntry` — Entry with a filtered dropdown suggestion list that appears below the widget; Tkinter has no native autocomplete
- `DateEntry` — date input widget with format validation and optional calendar picker popup; Tkinter has no date widget
- Expand custom frames
- More menu options

0.6.X Application Settings

Settings are stored per-project in `.VIS/settings.json` and accessed via `Project.settings`. The settings system provides a persistent key-value store with typed getters, a built-in settings UI panel that opens from the HostMenu, and developer extension points for adding custom settings panels.

**Storage and API:**

- `Project.settings.get(key, default)` — read a setting, returning default if not set
- `Project.settings.set(key, value)` — write a setting
- `Project.settings.save()` — persist to `.VIS/settings.json`; called automatically on Host close
- Settings are loaded on Host startup and available to all screens via `Project.settings`

**Window and display:**

- Default window size (width, height) — used by `WindowGeometry.setGeometry` if no explicit size given
- Default window alignment on open — matches `WindowGeometry` align options (`center`, `n`, `ne`, etc.)
- Remember last window size and position on close, restore on next open
- Minimum window size (`minsize`) — enforced globally unless overridden per screen
- Open fullscreen on launch toggle

**Host and tray:**

- Start Host with OS — toggle that enables/disables the startup registry entry
- Start minimized — Host starts hidden in tray rather than showing the window
- Remember open tabs — reopen the tabs that were open when the Host last closed

**Tab bar:**

- Tab bar position — top, left, bottom, or right
- Maximum simultaneous open tabs — enforced when opening new tabs
- Close confirmation — warn when closing a tab that has unsaved state (requires screen to implement `has_unsaved()` hook)

**Appearance:**

- Default font family and size — used by `fUtil.mkfont` when no explicit font given; feeds into styles system in 1.1.0
- Color scheme selection — placeholder for when styles system lands

**Notifications:**

- Enable/disable toast notifications globally
- Toast display duration in milliseconds

**Settings UI:**

- Built-in settings panel opens from HostMenu → Settings
- Settings panel is itself a tabbed interface — VIStk settings on one tab, developer's custom settings on additional tabs
- Developer registers a custom settings panel via `host.register_settings_panel(name, setup_fn)`
- Tray menu includes a Settings entry

0.7.X Defaults, Navigation, and Updating Tools

- Modify default imports
- Default templates
- Enable/Disable Keyboard Navigation
- More Navigation tools
- Update tools to ensure that updating VIS will not break code
- Tools to update created binaries

0.8.X Advanced Creation and Restoration

- Create VIS project in new folder
- Default .gitignore for VIS projects
- Repair broken screens to use templates

0.9.X Notifications

- `Toast` — non-blocking status overlay that auto-dismisses after a delay; respects the global notification enable/disable setting from 0.6.X

1.0.0 Full Release

- Explore tkinter styles
- - Setting screen styles
- - Creating global styles
- Sample VIS programs showing Icons, modules, Screens, menus

### Anytime

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
