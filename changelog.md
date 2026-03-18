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

**Screen lifecycle additions**

- `Screen.close()` — sends `__VIS_CLOSE__:<name>` to the Host via IPC; asks the Host to close a specific tab or Toplevel from within the screen itself
- `Project.set_default_screen(name)` — persists the default screen name to `project.json`; called automatically when the first screen is created via `newScreen`
- `newScreen` now prompts whether the new screen should open as a tab inside the Host (`tabbed` field stored in `project.json`)

**VINFO / project metadata**

- `VINFO.copyright` field — separate copyright string stored under `metadata.copyright` in `project.json`; falls back to the company name if not set; used by `InfoRow`

**Bug fixes**

- `TabBar._btn_click` drag suppression: `_drag_active` is now cleared inside `_btn_click` rather than `_on_drag_release`; previously the flag was always `False` by the time `_btn_click` ran (Tk fires `command=` after `<ButtonRelease-1>` bindings), so clicking after a drag would incorrectly focus the tab
- `Layout.rowSize` / `colSize` list mutation: both methods now copy the caller's list before inserting the leading `0` sentinel; previously they mutated the original list in place, which could corrupt reused list variables

**Hook rename**

- `on_activate()` / `on_deactivate()` renamed to `on_focused()` / `on_unfocused()` across all framework code and the screen template
- `Host` and `TabManager` look for the new names; the screen template stubs are updated accordingly

**Lifecycle hooks in module file**

- `on_focused`, `on_unfocused`, and `configure_menu` are now looked up in `modules/<screen>/m_<screen>.py` first; the screen script is used as a fallback so that existing screens without a separate hooks file continue to work
- `Host._import_hooks(scr)` — imports the hooks module for a screen; returns `None` if the file does not exist
- `TabManager._get_hook(name, hook_name)` — priority lookup across hooks module and screen module
- `TabManager.open_tab` now accepts a `hooks` keyword argument; the hooks module is stored in the tab dict and passed through all lifecycle calls

**Tab right-click context menu**

- Right-clicking any tab button shows a context menu with three options: **Open in new window**, **Force refresh**, and **Close**
- **Open in new window** closes the tab in the current `TabManager` and opens it in a new `DetachedWindow`; `TabBar.on_tab_popout` → `TabManager._on_popout_request` → `TabManager.on_tab_popout` → `Host._on_tab_popout`
- **Force refresh** re-imports and re-runs `setup(parent)` for the tab; hooks module is also re-imported; tab is reopened at its original position
- **Close** closes the tab as if its close button were clicked

**Tab drag-to-detach**

- Releasing a dragged tab outside all registered `TabBar` instances fires `TabBar.on_drag_detach`
- `Host._on_tab_detach` closes the tab from the main `TabManager` and opens it in a new `DetachedWindow`

**Tab drag-to-merge**

- All live `TabBar` instances register in the module-level `_TABBAR_REGISTRY` list; they deregister in `TabBar.destroy()`
- `TabBar.owner` attribute (set by `TabManager.__init__`) links each bar to its owning manager
- During drag motion the cursor is checked against all registered bars; the hovered bar shows its insertion indicator at the would-be drop position
- On release over a different `TabBar`, that bar's `on_drag_merge(name, source_bar, insert_idx)` is fired once
- `TabManager._on_merge_request` closes the tab in the source manager and re-opens it in the receiving manager via `open_tab` (which re-calls `setup(parent)`)

**DetachedWindow**

- New `VIStk.Objects._DetachedWindow.DetachedWindow` class — wraps a `Toplevel` + `TabManager` for popped-out or drag-detached tabs
- Pop out from a `DetachedWindow` (right-click or drag-out) sends the tab back to the main Host `TabManager`
- Closing a `DetachedWindow` runs `on_unfocused` on all its tabs before destroying them
- `Host._do_quit()` closes all `DetachedWindow` instances before tearing down the main window

**Drag ghost window and insertion indicator**

- Dragging a tab shows a semi-transparent `overrideredirect(True)` ghost `Toplevel` that follows the cursor; the ghost replicates the tab label (and icon if present) at 75 % opacity
- Tabs do not slide during a drag; position is committed only on release
- A thin coloured vertical bar (insertion indicator) appears inside whichever `TabBar` the cursor is over, showing exactly where the tab will land
- On release: reorder in the same bar at the indicated position / merge into another bar at the indicated position / detach into a new `DetachedWindow` if the cursor is not over any bar
- Dragged tab is dimmed while the ghost is live; normal colour is restored on release
- `TabBar.get_tab_idx(name)` — returns the 0-based position of a tab
- `TabBar.set_insert_indicator(idx)` / `TabBar.clear_insert_indicator()` — placed via `place()` over the packed tab strip using `_INDICATOR_COLOR` (dodger blue)
- `TabBar.open_tab` and `TabManager.open_tab` now accept `insert_idx` to insert at a specific position
- `TabManager.force_refresh_tab(name)` — close and reopen at same position

**InfoRow copyright formatting**

- `©` and the current year are automatically prepended to the copyright string if they are not already present

**InfoRow app version display**

- The project version (from `project.json` `metadata.version`) is shown on the right of the InfoRow alongside the FPS counter in the form `v1.0.0  |  30.0 fps`

**Bug fix: tab insertion positions**

- `TabBar._reorder_to_idx` no longer applies the erroneous `old_idx < idx` index compensation; the index from `_get_insert_idx_at` is already in "without-dragged-tab" space so no adjustment is needed — with two tabs open all three positions (before first, between, after last) now work correctly

**Drag ghost cursor alignment**

- Ghost window positions with the cursor at the exact pixel offset it had within the original tab button (`_drag_btn_offset_x/y` stored on drag start); same alignment is used to position the new `DetachedWindow` when a tab is released outside all bars
- `TabBar._last_drag_btn_offset_x/y` persists the offset after the drag ends so Host can read it in `_on_tab_detach`

**Empty TabBar drop zone**

- When a `TabBar` has no open tabs it shrinks to a 28 px visible drop-zone strip styled with `_BG_EMPTY`
- During a drag hover the strip highlights (`_BG_HOVER_EMPTY`) and shows a full-width horizontal insertion indicator at the bottom edge
- `_update_empty_state()` is called after every `open_tab` / `close_tab`

**DetachedWindow gets menu, info bar, icon, and geometry**

- `DetachedWindow` now contains a `HostMenu` (App → "Close Window"), a `TabManager`, and an `InfoRow` matching the main Host layout
- `InfoRow` FPS is broadcast from `Host.tick_fps()` via `_fps_listeners`; `DetachedWindow` registers and deregisters automatically
- Window icon is loaded from the project's default icon
- Window is sized to match the Host window and positioned so the cursor lands on the tab button at the same offset as during the drag; the window is withdrawn before placement and shown only after the exact position is calculated from measured widget layout offsets
- `DetachedWindow` is created as a peer `Toplevel()` (no explicit parent) so all application windows are at the same level

**Empty DetachedWindow does not close**

- When all tabs are removed from a `DetachedWindow` (e.g. dragged elsewhere), the window remains open showing the empty drop-zone strip; only the user's X button or `quit_host()` closes it

**Window title management**

- Host window title defaults to `project.title`
- Title updates to `"project: screen"` when a tab activates and resets to `project.title` when all tabs close
- Per-screen characteristic info string: `"project: screen — info"` format; also shown in the tab button label as `"screen — info"`
- Same title pattern applied to `DetachedWindow`

**Per-screen characteristic info (`set_tab_info`)**

- `TabManager.set_tab_info(name, text_or_var)` — set a characteristic string for a tab; accepts a plain `str` or a `tkinter.StringVar` (traced automatically; tab label and window title update live)
- Module-level `set_tab_info(frame, text_or_var)` helper exported from `VIStk.Objects` — call from inside `setup(parent)` using the received `parent` frame
- StringVar traces are removed automatically when the tab closes (no leaked callbacks)
- `TabManager.on_tab_info_change` callback: `(name, info)` — wired to Host and DetachedWindow

**Multiple instances of the same screen**

- Opening a screen that is already open anywhere creates a new tab with a `(2)`, `(3)` suffix on the display name
- `base_name` stored in each tab entry maps the display name back to the screen registry entry for re-import, refresh, and popout operations

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
