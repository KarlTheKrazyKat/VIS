# Changelog and Roadmap

## Released

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
- 

```
: can provide screennames instead of paths
```

- MenuItem(Button): now menuitem is the button and text autosizes
- 

```
            : will use screen.load() if provided with screenname
```

---

### 0.4.1 Screen Management

**Single-instance screens**

- New `single_instance` boolean field in each screen's `project.json` entry (default `false`)
- `Screen.__init__` reads and exposes `screen.single_instance`
- When `Host.open()` is called for a screen with `single_instance: true` that is already open anywhere (main window or any `DetachedWindow`), the existing tab is focused rather than creating a new instance; the `(2)` / `(3)` suffix logic is skipped entirely
- Set via `VIS edit <screenname> single_instance true`

`VIS rename <screenname> <newname>`

- Validates `newname` against the same rules as `VIS add screen` (no reserved words, valid identifier, no conflicts)
- Renames the screen's key in `project.json → Screens`
- Renames the script file on disk if the filename matches the old screen name pattern (`oldname.py` → `newname.py`); updates the `script` field accordingly
- Renames `Screens/<oldname>/` → `Screens/<newname>/`
- Renames `modules/<oldname>/` → `modules/<newname>/` and renames `m_<oldname>.py` → `m_<newname>.py` inside it
- Rewrites all `Screens.<oldname>.` and `modules.<oldname>.` import references inside the screen script
- Updates `default_screen` in `project.json` if it matches the old name
- Runs `stitch` automatically after rename so import blocks are regenerated clean
- `rename` and `Rename` added to `_RESERVED_VIS_COMMANDS`

`VIS edit <screenname> <attribute> <value>`

- Directly sets any attribute in the screen's `project.json` subdictionary
- Editable attributes: `script`, `release`, `icon`, `desc`, `tabbed`, `single_instance`, `version`, `current`
- Type coercion applied automatically by attribute:
  - `release`, `tabbed`, `single_instance` — `true`/`yes`/`1` → `True`; `false`/`no`/`0` → `False`
  - `icon`, `current` — `none`/`null` → `None`; any other string stored as-is
  - `version` — stored as string; must be valid `major.minor.patch` format
  - `script` — stored as plain string; rejects the value if the file does not exist in the project root
  - `desc` — stored as plain string
- Prints confirmation of old and new value
- Rejects unknown attribute names with a clear error rather than silently writing garbage keys
- Keeps the in-memory `Screen` object in sync immediately after writing
- `edit` and `Edit` added to `_RESERVED_VIS_COMMANDS`

---

### 0.4.2 Menus

**Three-layer menubar model**

The `HostMenu` menubar is now structured as three permanent layers in order:

1. **Built-in layer** — the "App" cascade (Close Window / Quit), always first, built automatically by `attach()`
2. **Project layer** — app-wide cascades defined once in `Host.py` at startup; never cleared during normal use
3. **Screen layer** — cascades contributed by the active tab via `configure_menu(menubar)`; all cleared automatically on tab deactivation

`HostMenu` **changes**

- `set_project_items(items, label)` — new method; appends one cascade to the project layer; calling it multiple times adds multiple project-layer cascades in order; these persist across all tab changes
- `clear_project_items()` — removes all project-layer cascades; intended for teardown, not normal use
- `set_screen_items(items, label)` — behaviour change: **accumulates** rather than replaces; calling it multiple times within a single `configure_menu` hook adds multiple screen-layer cascades side by side; still the right method for screen contributions
- `clear_screen_items()` — unchanged signature; now removes **all** accumulated screen cascades (tracked internally as a list of labels rather than a single slot)
- `_project_labels: list[str]` replaces nothing (new); `_screen_labels: list[str]` replaces the single `_screen_cascade` / `_screen_label` pair

**Usage pattern**

Project-wide items are set once in `Host.py` after `Host()` is created:

```
host = Host()
host.HostMenu.set_project_items([
    {"label": "File", "items": [
        {"label": "New",  "command": new_fn},
        {"separator": True},
        {"label": "Exit", "command": host.quit_host},
    ]},
    {"label": "Help", "items": [
        {"label": "About", "command": about_fn},
    ]},
], label="File")
```

Screen-specific items are contributed as before via `configure_menu`:

```
def configure_menu(menubar):
    menubar.set_screen_items([
        {"label": "Export PDF", "command": export_pdf},
        {"label": "Print",      "command": print_fn},
    ], label="Work Orders")
```

A screen that needs more than one cascade on the menu bar calls `set_screen_items` multiple times in one `configure_menu` call — all are cleared together on deactivation.

`VIS add screen <name> menu <menuname>`

- `Screen.addMenu(menu)` implemented (was a stub)
- Creates `modules/<screen>/m_<menuname>.py` containing a `configure_menu(menubar)` function pre-filled with a commented cascade template
- If `modules/<screen>/m_<screenname>.py` (the hooks module) already exists and does not define `configure_menu`, a delegation function is appended so the new menu module is wired in automatically
- If `configure_menu` already exists in the hooks module, import instructions are added as comments for manual wiring
- The generated file is a standard module file — developer fills in the item specs and it is picked up on next Host launch

**Installer & Release fixes**

- Replaced `from tkinter import *` with `import tkinter as tk` in `Installer.py` — the wildcard import shadowed the builtin `all()`, breaking the "Select All" checkbox logic
- Fixed `shortcut()`: used stale loop variable `i` instead of `name`, and called nonexistent `user_desktop_dir()` instead of `platformdirs.user_desktop_path()`
- Removed stale `i_file.close()` in `makechecks` that closed the root icon handle instead of per-screen handles
- Fixed `extal()`: only `chmod +x` actual binaries on Linux (no extension or `.sh`), not every extracted file
- Replaced `os.mkdir` with `os.makedirs(exist_ok=True)` in `adjacents()` so nested directories don't fail
- Deduplicated `installables` list to prevent duplicate checkboxes
- Replaced `source.index(i)` with `enumerate` in `makechecks` to avoid wrong indices with duplicate names
- Added `archive.close()` calls in quiet mode exit and GUI close button to release the zip handle
- Fixed prefix matching in extraction: `file.startswith(i)` → `file == i or file.startswith(i + ".") or file.startswith(i + "/")` to prevent false matches
- Fixed `_internal` filter: added trailing slash (`_internal/`) so files with `_internal` in their name are not incorrectly excluded from installables
- Fixed `previous()`: module-level `next_btn` reference is now updated via `global next_btn` so Back→Next round-trips don't crash
- Replaced four redundant extraction loops with a single-pass install + progress bar UI (filename above bar, installed/total size below-left, percentage below-right)
- Added version display: app version in installer header, per-screen versions next to checkboxes
- Fixed `binstall()`: takes a separate `selected_screens` parameter so installation proceeds regardless of shortcut checkbox state
- Replaced manual argument parsing with `ArgHandler`; added `--Help`, `--Path`, and `--Desktop` flags with enforcement that `--Desktop` and `--Path` require `--Quiet`
- `--Quiet` with no screen names now defaults to installing all screens
- Added `binaries.zip` existence check with user-friendly error message on missing archive
- Removed unused `shutil` import
- Fixed `newVersion()` in `_Release.py`: compared `self.Version == "Major"` (Version object vs string) → `self.type == "Major"`
- Added user confirmation prompt in `newVersion()` before applying a version change, with revert on cancel
- Re-enabled `newVersion()` call in `release()` (was commented out)
- Collapsed duplicated path logic in `clean()` into a single `pendix`/`out_dir` variable + loop
- Removed `os.chdir()` from `release()`; all paths are now explicit with `cwd=` parameter for subprocess calls

**Cached installer builds**

- `_Release.py` no longer runs PyInstaller for the installer on every release; the base installer exe is compiled once and cached in `.VIS/cache/`
- On subsequent releases, `binaries.zip` is appended directly to the cached base exe — `ZipFile(sys.executable)` reads the appended zip from the end of the file
- A SHA-256 hash of `Installer.py` + the icon file is stored alongside the cache; the base is only recompiled when the installer source or icon changes
- `Installer.py` tries self-contained mode first (`sys.frozen` + `ZipFile(sys.executable)`), falls back to external `binaries.zip` for development/testing

**Auto-launch after install**

- Optional "Launch \[AppName\]" checkbox on the completion page, checked by default
- On Close, launches the default screen binary (which starts the Host if not running); falls back to the first installed screen if the default was not selected
- Checkbox only appears when at least one screen was installed

**Documentation updates**

- `HostMenu` section updated to describe all three layers and the accumulate behaviour of `set_screen_items`
- `configure_menu` hook documentation updated with a multi-cascade example
- `VIS add screen <name> menu <menuname>` added to the CLI reference

---

### 0.4.0 Host and Tabbed Screens

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

- The project version (from `project.json` `metadata.version`) is shown on the right of the InfoRow alongside the FPS counter in the form `v1.0.0 | 30.0 fps`

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

**Per-screen characteristic info (**`set_tab_info`**)**

- `TabManager.set_tab_info(name, text_or_var)` — set a characteristic string for a tab; accepts a plain `str` or a `tkinter.StringVar` (traced automatically; tab label and window title update live)
- Module-level `set_tab_info(frame, text_or_var)` helper exported from `VIStk.Objects` — call from inside `setup(parent)` using the received `parent` frame
- StringVar traces are removed automatically when the tab closes (no leaked callbacks)
- `TabManager.on_tab_info_change` callback: `(name, info)` — wired to Host and DetachedWindow

**Multiple instances of the same screen**

- Opening a screen that is already open anywhere creates a new tab with a `(2)`, `(3)` suffix on the display name
- `base_name` stored in each tab entry maps the display name back to the screen registry entry for re-import, refresh, and popout operations

---

### 0.4.3 Split Layouts, Installer Uninstaller & Install Log

Allow the Host window's content area to be divided into multiple panes, each with its own `TabBar` and `TabManager`, with a draggable sash between panes. Two screens can then run side by side (or stacked) in a single window without spawning a `DetachedWindow`.

**Uninstaller**

- `Release.release()` generates an uninstaller executable alongside the installer
- Uninstaller reads `.VIS/install_log.json` to know exactly which files and shortcuts were created
- Removes all installed binaries, adjacent files, and desktop shortcuts
- Optionally deregisters from Windows Add/Remove Programs if the installer registered there

**Install log**

- Installer writes `.VIS/install_log.json` after a successful install — records every extracted file path, every shortcut created, the install location, and a timestamp
- The log is used by the uninstaller and by the update-in-place installer (0.4.4) to determine what is currently installed
- Quiet mode (`--Quiet`) also writes the install log

`SplitView` **widget**

- New widget (`VIStk/Widgets/_SplitView.py`) that replaces the single `TabManager` in `Host`
- Each instance wraps a `ttk.PanedWindow` (orient = `"horizontal"` or `"vertical"`) and holds two child slots; each slot is either a `TabManager` (leaf) or a nested `SplitView` (branch)
- This tree-of-panes model supports arbitrary split arrangements — splitting right and then down produces a `horizontal SplitView → [TabManager, vertical SplitView → [TabManager, TabManager]]`
- `SplitView.split(pane, direction)` — replaces the `TabManager` leaf at *pane* with a new `SplitView` containing the original pane and a fresh empty `TabManager`; `direction` is `"right"` or `"down"`
- `SplitView.remove_pane(pane)` — collapses the parent `SplitView` that contains *pane*, promoting the surviving sibling back to the parent's slot; if the root becomes a single `TabManager`, the `SplitView` wrapper is dissolved
- Sash positions are set to 50/50 by default; the user can drag them freely

**Focused pane**

- `SplitView.focused_pane: TabManager | None` tracks which pane the user last interacted with
- Clicking a tab in any pane sets that pane as focused; clicking anywhere in a pane's content frame also sets it focused
- The `HostMenu` and window title always reflect the focused pane's active tab — only one tab drives these at a time
- When the focused pane is removed (its last tab closed), focus transfers to the nearest remaining pane

**Right-click split actions**

Two new entries added to the `TabBar` right-click context menu:

- **Split right** — calls `on_tab_split(name, "right")` on the owning `TabManager`; `SplitView` handles this by splitting the pane horizontally and moving the tab into the new right pane
- **Split down** — same, with `"down"` and a vertical split

The existing "Open in new window" entry is unchanged; it still creates a `DetachedWindow`.

**Pane auto-removal**

- When a pane's tab count reaches zero (last tab closed or dragged elsewhere), the pane calls `on_pane_empty` on its owning `SplitView`
- The `SplitView` removes the empty pane and promotes the surviving sibling; if the root pane becomes empty there is nothing to promote — Host falls back to showing a single empty `TabManager`

**Drag-to-split**

- Dragging a tab into the outer 25% of any pane's content area shows a translucent blue overlay indicating a split zone (right, left, down, up)
- Releasing in a split zone creates the split and places the tab in the new pane
- Dragging to the center of a pane shows a full-pane overlay; dropping there adds the tab to that pane without splitting
- If a pane has only one tab, dragging it over its own pane shows the center overlay (no split possible)
- Tab bar insertion indicator shown alongside the center overlay to preview where the tab will appear
- Parent sash positions are preserved when performing nested splits (e.g. splitting the right pane vertically no longer shifts the left pane's width)

**Cross-window drag-to-split**

- Drag-to-split works across Host and DetachedWindows in both directions
- `DetachedWindow` is now wrapped in `SplitView` — same split, drop zone, and focus behaviour as the Host
- `SplitView._registry` (class-level list) enables cross-window zone detection; all registered SplitViews are checked during a drag
- Z-order aware: when windows overlap, only the frontmost window at the cursor position shows drop zones (uses Tk `wm stackorder`)
- Target window is lifted to the front as soon as the cursor enters its non-overlapping area during a drag; overlapping areas respect stacking order

**Focus-aware tab styling**

- Active tab in the focused pane is shown in a brighter grey; active tabs in unfocused panes are dimmer
- When a window loses OS focus (`<FocusOut>`), all pane focus indicators dim; they restore on `<FocusIn>`
- `SplitView._global_focused_pane` tracks the last-focused pane across all windows (Host and DetachedWindows)

**Global focus tracking**

- Clicking any widget inside a pane (buttons, entries, etc.) sets focus to that pane via a toplevel-level `<Button-1>` binding that walks the widget tree
- `Host._open_tab()` uses `SplitView._global_focused_pane` to open new tabs in the correct pane, even when the call originates from a DetachedWindow
- `Host.open()` only raises the Host window if the tab was opened there; if the tab was opened in a DetachedWindow, that window is raised instead

**Menu bar fixes**

- `HostMenu.set_screen_items()` now replaces shared cascades in-place (via `entryconfigure`) when the label matches an existing shared cascade, preventing duplicate File/Edit/View/Tools menus
- `HostMenu.clear_screen_items()` restores the original shared cascade menus
- `HostMenu.reset_overrides()` called on tab deactivate to prevent stale overrides from carrying over

`Host` **changes**

- `self.TabManager` replaced by `self._split_view: SplitView`; `TabManager` property returns `self._split_view.focused_pane` as a drop-in for the single-pane API
- `Host.open()` opens new tabs into the globally focused pane (may be Host or DetachedWindow)
- `Host._get_all_tab_names()` walks the full `SplitView` tree rather than a single `TabManager`
- Activate/deactivate/menu/title callbacks wired to all panes; focused pane arbitrates which tab drives `HostMenu` and the title bar
- `Host._on_tab_detach` and `Host._on_tab_popout` resolved through the originating pane's `TabManager`
- `Host._on_tab_split` handles within-pane splits, cross-pane splits, center drops, and cross-window drops

`DetachedWindow` **changes**

- Content area now wrapped in `SplitView` (was bare `TabManager`) — supports splits, drop zones, and focus tracking
- `tab_manager` property returns `self._split_view.focused_pane`
- `_on_tab_split` mirrors Host's implementation (within-window, cross-window, and center drops)
- `_on_close` iterates all panes in the SplitView tree, not just the focused pane

`TabBar` **changes**

- `on_tab_split: callable | None` — new callback `(name: str, direction: str, target_pane=None)`
- `on_drag_zone: callable | None` — new callback for drag-to-split zone detection during motion events
- Right-click menu gains "Split right" and "Split down" entries that fire `on_tab_split`
- Drag motion checks all registered SplitViews for drop zones when cursor is not over any TabBar
- Focus-aware `_tab_bg()` returns different colours based on pane focus state

---

### 0.4.3.1 Patch — Screen Splitting Fixes

- Fixed broken aspects of screen splitting introduced in 0.4.3

---

### 0.4.4 Tab Bar Enhancements, Installer Update & Integrity

**Tab bar enhancements**

- Tab bar position — top, left, bottom, or right
- Maximum simultaneous open tabs — enforced when opening new tabs
- Close confirmation — warn when closing a tab with unsaved state (requires `has_unsaved()` hook)
- Multiple tabs of the same screen — already implemented via `_unique_display_name()` (`Name (2)`, `Name (3)` suffixes); verify behaviour holds correctly with split layouts introduced in 0.4.3

**Update-in-place / patch installer**

- Installer detects an existing installation at the target path by reading `.VIS/install_log.json`
- Compares archive checksums against installed files and only extracts changed or new files
- Preserves user-modified files (e.g. settings) unless explicitly overwritten
- Significantly reduces install time for updates compared to a full reinstall

**Rollback on failure**

- If extraction fails mid-install, the installer cleans up all partially extracted files from the current run
- If updating an existing installation, the previous state is restored from a temporary backup created before extraction began

**Verify installation**

- Post-install integrity check confirms all expected files are present and match expected sizes from the archive
- Can be triggered manually from the installer menubar or via `--Verify` in quiet mode

**Installer menubar**

- Installer GUI gains a menubar with an "Options" dropdown
- Options menu entries: "Run Uninstaller" (launches the uninstaller if installed), "Verify File Integrity" (runs the verification check against `install_log.json`)

---

### 0.4.5 Installer Polish *(absorbed into 0.4.6)*

Implemented in-tree but not released as its own PyPI version. These features ship as part of 0.4.6.

**License / EULA page**

- Optional installer page that displays a license agreement loaded from a `LICENSE` or `EULA.txt` file in the archive
- "I agree" checkbox gates the Next button; installation cannot proceed without acceptance
- Skipped automatically if no license file is present in the archive

**Silent progress output**

- In `--Quiet` mode, print a progress bar to stdout using `\r` carriage returns instead of one line per extracted file
- Shows current file, percentage, and installed/total size inline

**Custom installer icon**

- `project.json` gains an optional `metadata.installer_icon` field
- If set, `Release.release()` uses it for the installer executable instead of the default app icon
- Falls back to the app icon if not specified

---

### 0.4.6 Screen Groups, Partial Installs & Missing-Screen Banner

*Released — absorbs every feature from 0.4.5.*

**Screen groups**

- `project.json` gains a `release_info.groups` block; each group maps a label to a `{description, screens: {screen_name: {default: bool}}}` entry.
- A screen belongs to at most one group; ungrouped screens continue to render as individual checkboxes (current behaviour preserved).
- Group rows in the installer render as a checkbox + label + right-side expand arrow. Expanding a group reveals indented child checkboxes with per-screen version labels.
- Clicking a group master toggles every child on or every child off (defaults only set the initial state). Tri-state (`alternate`) is shown when a group has a mix of checked/unchecked children; likewise for the top-level "All".
- Groups with no standalone-screen child actually present in the archive are hidden from the GUI — tabbed screens ship with the Host and cannot be toggled independently at install time.

**Per-screen dependencies**

- New schema: `Screens.<name>.requires: list[str]`, `suggests: list[str]`, and `warn_message: str|null`.
- On installer Next click the selected set is cross-checked; unmet `requires` trigger a 3-button dialog (Yes = auto-add + continue, No = continue anyway, Cancel = stay). Unmet `suggests` and required screens that aren't in the archive at all use a simpler OK/Cancel dialog. `warn_message` is folded into the dialog body.

**Partial install — developer-side subset release**

- `vis release -Groups <A,B>` builds an installer containing only the union of screens in the listed groups.
- `vis release -Screens <X,Y>` builds an installer containing only the listed screens. The two flags may be combined.
- The Host is always included. Excluded screens are never compiled and their entries are pruned from the archived `project.json`. Empty groups are dropped from the pruned schema.

**Quiet-mode group expansion**

- `installer.exe --Quiet <group_name>` expands the group into its default-selected members before running the existing archive-matching logic.
- A group containing at least one tabbed screen implicitly pulls in the Host (tabbed screens ride inside the Host exe).

**install_log.json**

- Each screen record in the log now carries a `"group"` field (the group name, or `null` for ungrouped / Host). Consumed by the runtime missing-screen detector.

**Runtime missing-screen handling**

- `Host.open()` now calls `VIStk.Structures.is_screen_installed(name)`before routing. When the binary is not present in the current installation, it shows an inline warning banner in the active `InfoRow` (via the new `InfoRow.show_banner(text, duration_ms, level)`) instead of silently failing.
- `is_screen_installed()` reads `.VIS/install_log.json` first and falls back to a filesystem probe for `.Runtime/<name>.exe` or `Screens/<name>.pyd`. Always returns `True` in dev mode (non-frozen).
- The banner uses the screen's `warn_message` when available; otherwise a generic "X is not installed. Reinstall and select it to enable this feature." string.

**CLI additions**

- `vis group add/remove/assign/unassign/default/list` — manage groups in `project.json`.
- `vis release -Groups A,B -Screens X,Y` — subset release.
- `vis edit <screen> requires "A,B"` / `suggests "C"` / `warn_message "…"`— list-typed attrs accept a comma-separated value; `warn_message`accepts a plain string or `none`/`null`.

**Absorbed from 0.4.5**

The License/EULA page, `\r` quiet-mode progress bar, and `metadata.installer_icon` land as part of this release.

---

### 0.4.7 Tab Identity Refactor

*Released.*

**Identity module**

- New `VIStk/Objects/_Identity.py` provides `new_id()`, a monotonic integer allocator used for every tab, pane, and window.
- IDs are process-unique but **not** persisted across runs; persistence (for features like "remember open tabs on restart") is out of scope.

**Tab IDs**

- `TabManager.open_tab(name, ...)` now returns the new `tab_id: int`(was `bool`) — hold this to address a specific instance.
- `TabManager._tabs` is keyed by `tab_id` (was the display label); each entry carries its own `display_name`, `base_name`, and `tab_id`.
- `TabManager` public methods (`close_tab`, `focus_tab`, `has_tab`, `force_refresh_tab`, `set_tab_info`) accept **either** a `tab_id`(`int`) or a display label (`str`). Label lookups are non-deterministic when duplicates exist.
- `TabManager.active` is now `int | None` (was `str | None`); use the new `TabManager.display_name(tab_id)` helper to resolve back to a label.
- `TabManager` ⇄ Host callbacks now pass `tab_id` instead of the display name: `on_tab_activate(tab_id, module)`, `on_tab_deactivate(tab_id | None)`, `on_tab_popout(tab_id)`, `on_tab_detach(tab_id)`, `on_tab_refresh(tab_id)`, `on_tab_info_change(tab_id, info)`, `on_tab_split(tab_id, direction, target_pane)`.
- `TabBar._tabs` is keyed by `tab_id` with the label stored in `entry["label"]`; `update_tab_label(tab_id, new_label)` replaces it.

**Pane and window IDs**

- `TabManager` gains `self.id: int` at construction.
- `_SplitNode` gains `self.id: int` so `SplitView._pane_parents` is now keyed by `.id` instead of Python's `id(...)` — stable across the object's lifetime, no risk of address reuse collisions.
- `DetachedWindow` gains `self.id: int` (currently used only for debug/logging; no lookups yet).

`SplitView.remove_pane` **focus restore — the bug fix**

- Before removing a pane, the SplitView records which `tab_id` was focused in the surviving pane subtree.
- `_snapshot_subtree` / `_rebuild_from_snapshot` preserve each tab's `tab_id` across destroy-and-rebuild by passing the original ID through the new `TabManager.open_tab(..., tab_id=...)` kwarg.
- After the rebuild the SplitView finds the new pane that now owns the recorded `tab_id` and restores focus there. Previously focus fell back to the first pane in left-to-right order, which failed when multiple panes held tabs with the same base name.
- `SplitView.find_pane_for_tab(tab_id)` replaces the former name-based helper.

`Host`

- `_find_tab_by_base(base_name)` now returns `(tm, tab_id)` instead of `(tm, display_name)`.
- `_get_all_tab_names` → `_get_all_tab_labels` (collects labels for `_unique_display_name` only; internal tracking uses IDs).
- `_open_counts` retired — tab IDs make multi-instance tracking trivial; label collisions stay a UX concern only.
- `Screen.close()` routes through the new ID-based `close_tab(tab_id)`.

**IPC**

- The original 0.4.7 scope mentioned `__VIS_CLOSE__` IPC. IPC is not being reintroduced — in-process `_HOST_INSTANCE` singleton stays the only navigation path. If IPC ever comes back it will use IDs natively.

**Out of scope**

- UUIDs for cross-process persistence — deferred to 0.6.X application settings when "remember open tabs" lands.
- Deregistering stale TabManager references from `Host.registered_tab_managers` / `DetachedWindow.tab_managers` after `remove_pane` — pre-existing bookkeeping leak, not part of this refactor.

---

### 0.5.0 VIS Widgets, Help Button & Popup Polish

**Released.** Adds general-purpose widgets, a one-line Help-button hookup, standard confirmation dialogs, and a flicker-free popup centring helper.

**VIS Widgets** — all exported from `VIStk.Widgets`:

- `Tooltip` — hover tooltip bound to any widget; `text` may be a `str` or zero-arg callable for state-dependent tooltips; cleans up its `after` callback on widget destroy
- `CollapsibleFrame` — frame whose body is hidden under a header button; pack children into `cf.body`; `cf.expanded_var` is a shared `BooleanVar`
- `AutocompleteEntry` — `ttk.Entry` with a filtered dropdown `Listbox`; `values` may be iterable or callable; `match="prefix"` (default) or `"contains"`
- `DateEntry` — entry + calendar-picker popup, no third-party dependencies; `get()` returns `date | None`; invalid manual input reverts on focus-out

**Confirmation dialogs:**

- `confirm(parent, *, title, message, yes="Yes", no="No") -> bool` — two-button Yes/No
- `confirm_discard(parent, *, title=None, message=None, name=None) -> "save" | "discard" | "cancel"` — three-button Save / Discard / Cancel; closing the window or pressing Escape returns `"cancel"`
- Both are modal, transient, and centred via `WindowGeometry.center_on` (no flicker)

**Help button & per-screen** `docs` **URL:**

- `HostMenu.add_project_command(label, command)` — adds a clickable leaf entry directly on the menubar (not a cascade); persists across all tab changes

- `Screen.docs: str | None` — per-screen URL field on `project.json` `Screens.<name>.docs`

- `Project.default_docs: str | None` — project-wide fallback (`defaults.docs`)

- `Project.resolve_docs_url(screen_name=None)` — runs the resolution chain (per-screen → project default → `None`)

- `Project.active_screen_name` property — returns the active tab's `base_name` (resolved via the 0.4.7 tab IDs)

- `VIStk.Objects.open_active_screen_docs()` — looks up the active screen's URL and hands it to `webbrowser.open`; returns `True` on dispatch

- `VIS docs` CLI:

  ```
  VIS docs set <screen_name> <url>
  VIS docs set --default <url>
  VIS docs clear <screen_name>
  VIS docs clear --default
  VIS docs list
  ```

- `VIS add screen` scaffolder writes `"docs": null` so the field is discoverable

- URLs are passed verbatim to `webbrowser.open` — no path normalisation; authors write fully-qualified URLs

**Popup flicker fix:**

- `WindowGeometry.center_on(window_ref)` — performs the canonical centre-on-parent math inside a `withdraw()` / `deiconify()` wrap and uses `update_idletasks()` (layout-only) instead of `update()` (which also processes the map request); the popup is never drawn at the OS default position
- Existing `setGeometry` is unchanged — no behavioural change for root-window callers
- `objects.rst` "Center a popup on its parent window" example updated

**Out of scope (deferred):**

- **Project Upgrade Tool** (`VIS upgrade`) — moved to 0.7 (already titled "Defaults & Navigation, update tools")
- **Color palette feature** — tracked separately for a later 0.5.x or 0.6.x
- `is_dirty` **auto-generated** `on_quit` — `confirm_discard` covers the manual case; the auto-wrapper can land later without an API break

### 0.5.1 Release Pipeline & Host Runtime

**Released.** Hardens the cross-platform release toolchain, flattens the install layout, and wires `loop()` into the Host's update path. No new public API.

- **Per-platform C compiler selection (#83):** forces MSVC on Windows so Nuitka doesn't fall back to its bundled zig toolchain (fixed the `init_fs_encoding` / `marshal data too short` launch crash, #35).
- **Pre-flight checks (#84, #88):** `Release._check_compiler()` / `_check_tools()` run before any compilation and abort with the exact install command when MSVC / gcc / pip / nuitka / pyinstaller are missing. The old per-release `pip install --upgrade` pass is gone.
- **Per-flag Nuitka build cache (#91):** `dist/` becomes deliverables-only; Nuitka's `.build/` / `.dist/` move to `build/<pendix>/`, so `-f Windows` and `-f Linux` builds no longer stomp each other's caches.
- **Dropped the PyInstaller launcher shims (#36, #37, #105):** Host and screen binaries stay at the install root; `VIStk/Structures/Launcher.py` deleted as dead code. ~30 MB smaller per install.
- **Uninstaller actually uninstalls (#34):** schedules a self-deleting `.bat` in `%TEMP%` that clears every directory at the install root except `Settings/`.

---

### 0.5.5 Outside Installable Media (OIM)

Lets a project ship non-VIStk installable media (e.g. a COM-registered SolidWorks/.NET add-in) *inside* the same installer, surfaced as an opt-in install choice with a developer-supplied post-extract script.

**Folder convention** (`<project>/OIM/<name>/`, no `project.json` registration — discovered like `commands/`):

- `manifest.json` *(optional)* — `label`, `description`, `default` (default `false`), `required` (default `false`).
- `media/` — the payload; staged into the install dir, then the script installs it.
- `icon/<image>` — the checkbox icon shown in the installer.
- `script/install.py` *(optional)* — run **in-process** in the installer's interpreter after the entry's media is extracted.
- `script/uninstall.py` *(optional)* — persisted to `runtime/.VIS/oim/<name>/` and run by the Uninstaller on a full uninstall.

**Release pipeline**

- `Release.clean()` copies `OIM/` to the install **root** of the build (`self.final/OIM/`, not `runtime/`) so it rides into `binaries.zip` via `root_dir=self.final` while staying out of the host-selected `runtime/` catch-all. `VINFO.p_oim` added as the canonical path.

**Installer**

- OIM entries are discovered by scanning the appended archive for `OIM/<name>/…` and rendered as `kind:"media"` rows under an **Additional Software** header on the installables page; required entries render checked + disabled, optional default to off. Integrated into the master **All** / tri-state accounting (required entries excluded so *All* can still reach fully-off).
- Selected media are handled by `_install_oim()` (shared by GUI and `--Quiet`): stage → exec `install.py` → on success persist `uninstall.py` + record in `install_log.json` (`"oim"` array, merged on repair) + delete the staged folder; the empty `OIM/` root is then removed. A failing script logs to `vis_installer.log`, is surfaced in the status line, and **never** rolls back the committed app install.
- Script execution is **in-process `exec()`** (the frozen installer can't shell out to a system Python, and `sys.executable` is the installer). Scripts receive `INSTALL_ROOT`, `RUNTIME_DIR`, `MEDIA_DIR`, `OIM_NAME`, `APP_TITLE`, and a `log()` callable, inherit the installer's `--uac-admin` elevation, and must be idempotent (re-run on every install/repair).
- `--Quiet` selects required media always, all media on a bare `--Quiet`, and named media otherwise.

**Uninstaller**

- `run_oim_uninstall()` execs each recorded `uninstall.py` (same in-process model + context) **before** the file sweep, on a full uninstall only — closing the orphaning gap for media that registers state outside the install dir (COM/regasm, GAC, plugin folders).

---

### 0.6.0 Application Settings

Per-project application settings stored in `.VIS/settings.json`, accessed via `Project.Settings`, surfaced through a built-in tabbed Settings window.

**Storage & API** — `VIStk/Structures/_Settings.py`

- `ProjectSettings` — `project.Settings.get(key, default)` / `.set(key, value)` / `.save()`, backed by `.VIS/settings.json` (new `VINFO.p_settings` path; `Project.Settings` attached in `Project.__init__`).
- `get` resolution order: stored override → explicit `default` arg → framework `DEFAULTS` table → `None`.
- **Default file materialized** — a full `settings.json` (every key at its default) is generated at `VIS new` scaffolding and on first Host launch (`ProjectSettings.ensure_file()`, idempotent — never clobbers an existing file), so all options are visible and hand-editable. In memory only genuine overrides are tracked (`reset()` / `in` mean "explicitly customised"); `save()` writes the complete resolved set back. A missing or corrupt file falls back to defaults without crashing. All `DEFAULTS` values are immutable (no shared-reference mutation).
- Also `effective()` (full resolved map, for the UI), `reset(key)`, `__contains__`, and a `dirty` flag — the Host skips the shutdown write when nothing changed.
- Saved automatically on Host shutdown via both the `quit_host` and last-window-close paths. The shutdown capture commits **only after** every window has closed without veto, so a vetoed quit leaves settings untouched.

**Window & display**

- `window.default_width` / `default_height` / `default_align` (center + 8 compass points) / `min_width` / `min_height` applied to the session's first window.
- `window.remember_geometry` — capture the primary window's size + position on close, restore it on next launch.
- `window.fullscreen_on_launch` — open the first window maximized.

**Host & startup**

- `host.start_with_os` — toggles the Windows startup-registry entry (`_register_startup` / `unregister_startup`), reconciled on Save. Disabled (and not persisted over) on non-Windows.
- `host.remember_tabs` — record the open screens on close and reopen them on next launch. The `max_tabs` limit is bypassed during restore so a remembered session isn't truncated; screens no longer present in the project are dropped silently (no missing-screen banner).

**Appearance**

- `appearance.font_family` / `appearance.font_size` applied at launch to Tk's named fonts (`TkDefaultFont`, `TkTextFont`, `TkMenuFont`, `TkHeadingFont`, `TkFixedFont`), which default and ttk widgets inherit.
- `appearance.color_scheme` — stored placeholder for the future styles system (no effect yet).
- Live re-styling of already-open windows is deferred to **0.6.1**.

**Notifications**

- `notifications.enabled` (stored; consumed by the 0.9 Toast widget) and `notifications.duration_ms` — the latter is now the default duration for `InfoRow.show_banner` when a caller omits it.

**Settings UI** — `VIStk/Widgets/_SettingsWindow.py`

- Modal, tabbed (`ttk.Notebook`) window opened from a framework-provided **HostMenu → Settings** entry present on every window. **Save** / **Cancel** / **Restore Defaults**; controls seeded from `effective()`; Save rejects negative / non-numeric numeric input.
- `host.register_settings_panel(name, setup_fn)` — apps contribute their own tabs; `setup_fn(parent_frame)` builds into the tab body (mirrors a screen's `setup`). A panel that raises shows an inline error rather than a blank tab.

**Scope notes**

- The spec's **tray** items — start-minimized-to-tray and a tray Settings entry — were dropped: the 0.5.3 always-Host refactor removed the system tray, so the Host now lives only as long as its windows. The stale tray documentation has been corrected.
- Remember-open-tabs is a **screens-only** restore: the open screens reopen as tabs in one window; split-pane layouts and multiple windows are not reconstructed.
- Window-size settings apply to the session's primary window; drag-detached / popped-out windows keep the default size.

---

### 0.6.2 v-Prefixed Widgets

A family of `v`-prefixed widgets in `VIStk.Widgets` that subclass the **classic** tk widgets (so per-instance `bg`/`fg`/`font` work — ttk can't) and (1) inherit visual properties from their parent by default and (2) optionally render rounded corners. They consolidate the rounded "pill / chip / card" pattern that callers otherwise hand-roll per screen with Canvas polygons. (Issue #187.)

**`vWidget` base** — `VIStk/Widgets/_vWidget.py`

- A pure mixin (subclasses `object`, never `tk.Widget`), combined with a native widget via multiple inheritance: `class vLabel(vWidget, Label)`. `vWidget.__init__` runs first in the MRO — computes inheritance, pops the rounded kwargs — then cooperative `super().__init__()` creates the underlying Tcl widget exactly once. A `vLabel` is genuinely both a `vWidget` and a `tk.Label`.
- **Parent inheritance** — each subclass sets `_INHERIT` (e.g. `("background","foreground","font")`); any of those the caller omits are filled from the parent at construction. Explicit options always win. Reads classic parents via `cget` and ttk parents via `Style().lookup(winfo_class(), …)` (the "f_steps trick", with a `SystemButtonFace` fallback). Snapshot at construction; `refresh()` re-pulls on demand.
- **Rounded corners** — opt-in via `radius` (`0` → a plain native widget, no extra machinery). The classic widgets are always rectangular, so the rounded look is an anti-aliased PIL rounded-rectangle image (4× supersampled, Lanczos-downscaled) regenerated on `<Configure>`; corners are painted with the parent background so they blend on a solid-colour parent. Colours resolve through `winfo_rgb`, so every Tk colour name works (`greyNN`, hex, `SystemButtonFace`). Optional `outline` / `outline_width` / `corner_bg`. Subclasses choose where the image is composited via `_prepare_rounded` / `_paint`.
- **Runtime recolour & pixel sizing** — `configure()`/`config()` repaints the rounded fill live when a paint-affecting option changes (`_REPAINT_OPTS`, default `bg`/`background`; previously a rounded widget only repainted on resize/hover). A 1×1 transparent placeholder image is installed in rounded mode so `width`/`height` are honoured in **pixels** from the first frame (Tk reads them as character cells until a widget has an image), letting callers size rounded chips/pills in pixels without a flash.
- **Clobber-proof resize repaint** — the `<Configure>` repaint is installed on a dedicated bindtag (`_RENDER_TAG`) routed through one class-level dispatcher, so a caller's own `widget.bind("<Configure>", fn)` *without* `add="+"` (e.g. wiring up `fUtil.autosize`) no longer silently replaces it and leave the widget rendering square.
- **Caller `image=` in rounded mode (#188)** — a rounded widget owns its single Tk image slot for the fill, so previously a caller-supplied `image=` was silently clobbered (the icon never appeared at `radius > 0`, though it worked at `radius=0`). Now the glyph is popped at construction (and on runtime `configure(image=…)`), coerced to a PIL image (`_glyph_to_pil` — accepts a PIL `Image` **or** an `ImageTk.PhotoImage`, recovered via `ImageTk.getimage`), and `alpha_composite`d onto the PIL fill on *every* repaint via `_composite_glyph` — so it rides along through hover (`active_fill`), `disabled_fill`, resize, and `bg`/`state` recolours. The glyph keeps its native size, downscaled (aspect-preserving) only when it overflows the widget interior. **The glyph is positioned by the widget's `anchor` option** — `"center"` (the default) centres it as before, but `"w"`/`"e"`/`"n"`/`"s"` and the corner anchors (`"nw"`, `"ne"`, `"sw"`, `"se"`) pin it to that edge/corner, so callers place the image wherever they want instead of being stuck at centre (edge/corner anchors are inset by the corner-clearing margin `ceil(r·(1−1/√2))` so the glyph stays off the rounded arc). Fixes rounded `vButton` and `vLabel` identically (both share the base `_render_rounded`/`_paint`); replaces the `_IconButton` subclass workaround PYWOM's LibrarySearch carried. Containers (`vFrame`/`vLabelFrame`) override the render path and are unaffected.
- `make_rounded_image(...)` is exported for direct use; `vWidget` is exported so callers can build further v-widgets.

**`vLabel`** — `VIStk/Widgets/_vLabel.py`

- `class vLabel(vWidget, Label)` — inherits `bg`/`fg`/`font`. Rounded mode draws the text centred over the rounded fill (`compound="center"`, zero border/pad so the image exactly covers the widget and can't trigger a size feedback loop). Drop-in for `tkinter.Label` at `radius=0`.

**`vButton`** — `VIStk/Widgets/_vButton.py`

- `class vButton(vWidget, Button)` — inherits `bg`/`fg`/`font`; `command`/`invoke()` and all native button options pass through. Rounded mode flattens the relief (`relief="flat"`, `overrelief="flat"`), shows a hand cursor, and accepts an optional `active_fill` that repaints the fill on hover (`<Enter>`/`<Leave>`), mirroring the chip-button pattern PYWOM hand-rolls today. A `disabled_fill` + `configure(state="disabled")` greys the fill, swaps the cursor, and gates the click (native `state` already blocks `invoke`) — a drop-in for PYWOM's `set_chip_enabled`. Drop-in for `tkinter.Button` at `radius=0`.

**`vFrame`** — `VIStk/Widgets/_vFrame.py`

- `class vFrame(RoundedContainer, vWidget, LayoutFrame)` — keeps the `.Layout` helper; inherits `background` only (Frames have no fg/font). The frame's `bg` is the **fill**; rounded mode draws one anti-aliased rounded rectangle (fill + optional `outline`) onto a *lowered* background `Label`. Two layers keep the corners clean:
  - **Inset every child (all geometry managers).** A Tk child is an opaque rectangle with no per-widget transparency, so a child that reaches a rounded corner squares it off. `vFrame` insets **every** child by `ceil(radius·(1 − 1/√2))` ≈ `0.293·radius` (size-aware as the corner clamps on small frames), regardless of how it was placed: `.Layout.cell`, plain relative `place`, `pack`, or `grid` (the caller's own `padx`/`pady` is preserved via a one-time captured base). The inset is **invisible** when the child shares the frame's `bg` (the fill reads as continuous to the edge — the inherited default). Pass `inset=` (or set `.Layout.margin`) to pull content further in, or `0` for none.
  - **Sub-pixel corner patch (drawn on the child).** The inset is whole-pixel, so a child's corner can still land a fraction of a pixel proud of the border — its *fill* then shows where the *outline* (or corner background) should be, notching the border. That can't be repainted on the frame (the border is on the lowered image *behind* the child, which covers it at that pixel), so the patch is drawn **on the child**: a ~1px `Label` at the child's own corner, above its content, showing an exact crop of the border image for that spot (outline colour where the outline is, corner-blend colour beyond). It is sized to the *actual* overhang past the fill arc (`r − outline_width`), so it never reaches the child's text, and only the corners a child actually occupies are patched (`_refresh_corner_marks`).

  Drop-in for `LayoutFrame` at `radius=0` (no inset, no painting). Children added at runtime are picked up on the next resize, or immediately via `refresh()`. (Corner blending assumes a solid-colour parent.)

  *History:* an earlier build floated **opaque, radius-sized** corner pieces over content, which covered child text at the corners; it was replaced by insetting all children. This revision adds the tiny per-corner patch back — but minimal (≈1px, sized to the real overhang) and drawn *on the child above its content* rather than as a big overlay — to close the sub-pixel notch that whole-pixel insetting leaves on outlined frames.
- **`Layout.margin`** (`VIStk/Objects/_Layout.py`) — a uniform pixel inset on a `Layout`: every `cell()` (and `apply()`) shrinks away from the frame edges by `margin`, while inter-cell boundaries stay shared. Layered onto the relative geometry as a fixed pixel offset, so it stays correct on resize. Used by rounded `vFrame` to keep content clear of the corners.

**`RoundedContainer`** — `VIStk/Widgets/_vContainer.py`

- Shared rounded-corner machinery for the v-prefixed *containers* (`vFrame`, `vLabelFrame`), extracted so the two differ only by native base. Provides the lowered fill-image render, the size-aware inset of **every** child across all geometry managers, and the per-child sub-pixel corner patch. A container mixes it in *before* `vWidget` (`class vFrame(RoundedContainer, vWidget, LayoutFrame)`) so its `_prepare_rounded`/`_render_rounded` win the MRO; `_setup_container(inset)` is called from the host `__init__`. `vFrame`'s behaviour is byte-for-byte unchanged by the extraction (verified by the existing tests). A `_skip_child(child)` hook lets a subclass exclude children the machinery must not touch (the lowered background label, and `vLabelFrame`'s title).

**`vLabelFrame`** — `VIStk/Widgets/_vLabelFrame.py`

- `class vLabelFrame(RoundedContainer, vWidget, LabelFrame)` — a drop-in `tk.LabelFrame` (every native option/method works: `text`, `labelanchor`, `labelwidget`, `fg`/`font` for the title, `relief`, `bd`, …) with the v-widget conveniences. Inherits `background`, `foreground` **and** `font` (it has a title); carries a `.Layout` like `vFrame`. At `radius=0` it is an ordinary `LabelFrame`.
- **Rounded title, the hard part.** A `LabelFrame` lays children out in a *content area* below the title band, so a background image placed there (relative to the content area) misses the top/bottom border — only the side borders show. Rounded `vLabelFrame` instead floats the lowered fill image across the **whole** frame (placed with the measured content-origin offset negated, `relwidth/height` cleared so `place()` doesn't double the size) and keeps the title on top by routing it through a **labelwidget**: an internal `Label` mirroring `text`/`fg`/`font` (created lazily when there's title text), or the caller's own `labelwidget`, lifted above the fill. Tk still positions it per `labelanchor`, so the title breaks the rounded border exactly like a native label. `configure(text=/fg=/foreground=/font=)`, `cget(...)` and `widget["text"]` transparently proxy to that title; `bg` changes keep the title chip on-fill.
- Children are inset off the rounded corners by the shared machinery (the native title widget is excluded via `_skip_child`). The native rectangular border is flattened (`bd=0`, `relief="flat"`) so the rounded outline is the only chrome — a rounded box almost always wants an `outline`. Registered in `Widgets/__init__.py` and `_vtypes.py` (`_LabelFrameKw`).

**`vImage`** — `VIStk/Widgets/_vImage.py`

- `class vImage(vWidget, Label)` — an **image-only** widget (the mirror of `vLabel`'s "text with an optional image"). Loads through the existing `Objects/_VIMG.py` `VIMG` object, so `Project().p_images` resolution, the glob-prefix fallback and `absolute_path` behave exactly as everywhere else `VIMG` is used; `vImage` owns only the Tk rendering, so a single clobber-proof `<Configure>` handler refits instead of competing with `VIMG`'s own resize bind. Exposes the loaded `VIMG` as `.VIMG`, and `set_path(path, absolute_path=…)` swaps the source and repaints.
- **Inheritance** — `background` only (an image carries its own pixels; no fg/font). The inherited bg fills the aspect-ratio letterbox bars — and, in rounded mode, the transparent corners — so the image blends on a solid parent.
- **Fit** — default `fit=True` *contains* the image in the live widget size, re-fitting on resize (the `VIMG` "fill" behaviour). `size=(w, h)` contains it in a fixed pixel box; `fit=False` shows it at natural size. All modes preserve aspect ratio (contain, never distort).
- **Rounded corners** — opt in with `radius` > 0: an anti-aliased rounded mask (4× supersampled, multiplied into the image's own alpha so source PNG transparency is preserved) makes the corners transparent, so the widget's inherited `bg` shows through and re-blends on a `bg` change with **no** re-render. Optional `outline`/`outline_width` strokes the rounded edge. `round_image(img, radius, outline=…)` is exported for direct use. Drop-in image `Label` at `radius=0`.

**Native-option discoverability** — tkinter hides each widget's options behind `**kw` and only lists them in the `__init__` docstring, so `vButton(...)` gave callers no hint that `command`/`relief`/`anchor`/… are accepted. Both surfaces now expose them:

- **`help()` / REPL / Sphinx** — `vWidget.__init_subclass__` lifts the native option block straight from the tk base's `__init__.__doc__` (Label/Button "STANDARD OPTIONS", Frame "Valid resource names") and appends it to each v-widget's `__init__` doc at class-creation time. Authoritative and always in sync with the installed Tk.
- **Editor hover/autocomplete** — each `__init__` types `**kwargs: Unpack[_XKw]` (`VIStk/Widgets/_vtypes.py` `TypedDict`s mirroring `<widget>.keys()`), so Pylance/PyCharm list every native option next to the v-widget's own `radius`/`outline`/… params. The `Unpack`/`_vtypes` imports are `TYPE_CHECKING`-only (annotations are strings under `from __future__ import annotations`), so there's zero runtime cost and no new runtime dependency (`typing_extensions` is only needed by a type-checker running on Python < 3.11).

**Packaging** — `pillow` added to `pyproject.toml` dependencies (already used by `Objects/_VIMG.py`, previously undeclared).

### 0.6.3 AutocompleteEntry Popup Scoping & Tracking

Two fixes to `AutocompleteEntry`'s suggestion popup (`VIStk/Widgets/_AutocompleteEntry.py`).

- **Popup scoped to its own window (#189)** — the suggestion popup was a borderless `Toplevel` pinned with `attributes("-topmost", True)`, which is *global to the desktop*: while suggestions showed it floated above **every** application, so any Alt-Tab / notification / focus race left an orphan-looking box over whatever app was now active. It is now `transient(top)` + `lift(top)` to its own toplevel — above its own window (and out of the taskbar) only, never over other applications. `overrideredirect` stays (borderless is right for a dropdown).
- **Popup tracks window move/resize** — the popup's geometry was computed once in `_show_popup`, so moving or resizing the parent window while suggestions were open left the popup stranded at stale screen coordinates. A `<Configure>` handler on the toplevel now re-runs positioning (extracted into `_position_popup`), keeping the popup glued below the entry and matching its width. Positioning is deferred to `after_idle` because a toplevel `<Configure>` fires *before* the geometry manager re-lays-out the entry — reading the entry width synchronously would use the pre-resize value.
- **Clobber-proof cleanup** — the `<Configure>` handler is routed through a per-instance private bindtag (`_AutocompletePopup<id>`) rather than a direct `top.bind(...)`, so hiding the popup removes only our own binding and can never clobber another `<Configure>` handler on the window (and sidesteps the Tk `unbind`-by-funcid behaviour that differs across versions). Mirrors the 0.6.2 "clobber-proof resize repaint" approach.

---

## Planned

### 0.5.2 Screen Isolation (per-tab namespaces, wrapper `.pyd`s, always-Host)

Implemented in **PR #141** (merged to `master`, pending PyPI release). Isolates each open tab's Python state and collapses the per-screen build to a single wrapper `.pyd`.

**Per-tab namespaces**

- Each open tab gets an isolated namespace registered as `Screens.<name>__tab<id>` / `modules.<name>__tab<id>`, built by `TabManager._build_namespace` via a routing `__import__` that redirects absolute imports to the per-tab variants.
- A `_PerTabProxy` stands in for the top-level `Screens` / `modules` bindings, so attribute access (`Screens.<X>.f_wonum.build`) walks into the per-tab namespace instead of the shared package.
- Fixes the bug where two tabs of the same screen shared module-level state (`StringVar`s, global widget refs, loaded data).

**Wrapper `.pyd` build**

- The release pipeline collapses each screen's three former artifacts (entry `.pyd` + `Screens/<name>.pyd` + `modules/<name>.pyd`) into a single wrapper `runtime/<stem>.pyd` holding marshalled bytecode for the entry script and every `f_` / `j_` / `m_` in an `_EMBEDDED` dict.
- `TabManager` reads code from `_EMBEDDED` in release mode and from source files in dev mode (discriminated by `scr.script_path`).
- `_compile_one_screen_package` / `_compile_one_module` and the `--include-package` / `--nofollow-import-to` dance they required are removed; `runtime/` is auto-wiped at the start of every full release.

**Always-Host model**

- Standalone per-screen `.exe`s are dropped — every screen opens through the Host as a tab or chromeless `DetachedWindow`; one `.exe` ships per project (the Host).
- The `release` field on `Screen` gates Start Menu shortcut creation (installer change).

> Note: an earlier "Screen Isolation" plan (a cross-screen import linter `_Lint.py`, a `shared/` package convention, per-screen `--include-package`) was **superseded** by the per-tab-namespace + wrapper-`.pyd` design above and is **not** part of #141 — the linter / `shared/` convention remain possible future work.

---

### 0.5.3 Single-Instance Host, CLI Commands & Cross-Platform Packaging

Built on PR #143 (`host-single-instance`) — implemented and verified, not yet released. One Host per project/user, a non-GUI **CLI command** path invoked as a bare subcommand (`<project> <command>`), and the cross-platform packaging to ship it.

**Single-instance Host**

- Binding a per-project/user `127.0.0.1` port is the mutex: the first launch is the primary Host; a later `<project>.exe <Screen>` forwards its open request to the running Host (which raises the window) and exits — no second process.
- **dev/compiled lock domains (#151):** the port keys on `title + user + mode`, where mode is `dev` vs `compiled` (via `is_compiled()`, below). A `python .VIS/Host.py` dev Host and a compiled `<title>.exe` are separate single-instance domains and run side by side; each CLI client routes to its own.
- **Compiled-mode detection (`is_compiled()`):** one helper in `_VINFO` answers the question every dev/compiled call site actually asks — *is `sys.executable` the bundled app binary, or a python interpreter?* — keyed on the executable basename (`python*` ⇒ dev). It replaces `sys.frozen` at the sites that misfired under Nuitka `--standalone` (which, unlike PyInstaller / Nuitka-onefile, does **not** set `sys.frozen`): `getPath()` — so a CLI command typed in an arbitrary directory still finds `.VIS/` instead of the Host entry script dying on `import modules.*` before it can route — plus `Host._register_startup` (run-at-login command) and `Screen.load` (no-spawn guard). `_compute_lock_port` and the `host.txt` template route through it too, so there's a single source of truth.

**Host CLI commands**

- Invoke as a **bare subcommand**: `<project> <command>` (e.g. `WOM ping`) — no mode flag. A registered screen name still launches the GUI (the screen registry is checked first); any other first word is a command, and an unknown one prints a usage error listing `commands.__all__`.
- A command is a project file **`commands/c_<name>.py`** with an entry **`_c_<name>(args)`** (mirrors the `_m_<name>` convention). `_c_<name>` runs **on the running Host** and returns a `(callable, args)` continuation for the terminal side, or `None`; `args` is the words after the command name.
- Discovery via **`commands.__all__`** — built dynamically in dev (`commands/__init__.py` scans `c_*.py`), baked **static** into `commands.pyd` by `VIS release`. The Host imports `commands.c_<name>` lazily.
- VIStk ships **no** commands. `VIStk.Objects._cli` is just the transport — a continuation prints terminal-side by ending with the builtin `print` (it crosses as `builtins:print`); no VIStk wrapper needed.
- **No Host running:** a CLI command still runs — in-process and **headless** (no Tk, no socket; `Host._cli_run_local`), and never launches the GUI as a side effect of being the first instance. The continuation chain executes locally with `_HOST_INSTANCE` left `None`, so commands that read live Host state degrade gracefully (e.g. `ping` reports `open_windows=0`). An unknown command still prints the usage error.

**CLI help, aliases & screen intercepts**

- **`--help` / `-h`:** `<project> --help` lists every screen and command as `name | alias…` + short help; `<project> <cmd> --help` prints the long help. A `c_*.py` documents itself with **`__help__`** (a list of strings: `[0]` short, `[-1]` long; one string ⇒ short == long). Answered terminal-side before any Host/lock — no running Host needed. Screens with no `c_<Screen>.py` get auto help `Launches the <Screen> screen.`; missing command help degrades to `(no description)`.
- **Aliases (`__alias__`):** a str or list on a `c_*.py` gives a command **or** a screen alternate names — `__alias__ = "pong"` in `c_ping.py` makes `WOM ping` == `WOM pong`; `__alias__ = "ewo"` in `c_WorderEditor.py` makes `WOM ewo` open WorderEditor. Resolution: exact name (screen → command) first, then alias, case-insensitive; real names beat aliases. `_resolve_startup` (replacing `_resolve_startup_screen`/`_args`) routes the first non-flag token through this registry.
- **Screen intercepts (`_c_<Screen>`, Option 2):** a `c_<Screen>.py` may add an `_c_<Screen>(args)` intercept that runs on the Host before the screen opens — return `None` → launch with the original args, a `list` → launch with transformed args, a `(callable, args)` continuation → run terminal-side as a CLI response and do **not** open the screen (e.g. arg validation). Host-running routes through `Host._run_screen_intercept` over the exchange; no-Host runs it in-process, then becomes the GUI Host with the resulting args (or stays headless for a continuation). `_resolve_command(<screen>)` doubles as the intercept lookup.

**CLI transport — continuation-passing two-pump**

- Two roles, same shape: **H** (running Host, Tk loop) and **T** (terminal-launched). Each has a queue, a pump, and a socket bridge.
- Continuations cross the socket **by reference** (`module:qualname`, re-imported on the far side — both ends are the same binary). Closures can't cross; args must be JSON-serializable.
- Every message gets exactly one response; T exits when its queue is empty and no request is outstanding. H-side functions must not block (Tk loop); T-side may block (`input()`).

**Cross-platform packaging**

- **Windows two-binary:** `<title>.exe` (PE subsystem 2 = GUI, no console flash) + `<title>.com` (subsystem 3 = console, shell waits + stdio), produced by copying the exe and patching the PE subsystem byte (`_Release._patch_pe_subsystem`). Typed `<title>` resolves to `.com` first via `PATHEXT`.
- **Linux daemonize (#152):** a GUI launch `fork`+`setsid`s so the terminal is freed and the Host runs detached (daemon stdio → `<tmpdir>/<title>_host.log`); CLI commands stay foreground so their stdio works — the Linux mirror of the console `.com`.
- **`commands.pyd` build:** `nuitka --module --include-package=commands` over a build copy carrying a static `__all__`, run from the build-copy parent so the source and copy `commands` packages don't collide.

**Shared-package fix (#150)**

- `compile_shared()` shipped *all* of `site-packages` when a `hidden_imports` entry was a single-file module (e.g. `six` → `os.path.dirname(six.py)` resolves to site-packages). Single-file modules are now detected and shipped as one sourceless `runtime/<pkg>.pyc`.

---

### 0.5.4 ContextMenu Widget

A reusable right-click popup menu so screens stop hand-coding the `tkinter.Menu` + `tk_popup` boilerplate (the pattern `TabBar` carries today).

**`ContextMenu`**

- Thin wrapper over the *native* `tkinter.Menu` — keyboard navigation, hover submenus, click-outside dismissal and screen-edge clipping all come from Tk for free. Renders as the classic system menu, not a ttk-themed widget.
- Passing a `widget` auto-binds the right-click (`button="<Button-3>"` default); omit it and drive the menu manually via `show(event)` / `popup(x_root, y_root)`.
- `items` may be a list of item-spec dicts **or** a callable `(event) -> list`, re-evaluated on every popup so the menu can reflect what was clicked (e.g. the step under the cursor).
- Item spec reuses the VIStk menu convention shared with `HostMenu`: `{"label", "command"}` leaf, `{"label", "items": [...]}` cascade, `{"separator": True}`. Per-item extras: `"state": "disabled"`, `"accelerator"`, and `"checkbutton"` with `"variable"`.
- `set_items(items)` swaps the source; owned `Menu` objects are rebuilt per popup and destroyed with the bound widget.

> Note: this is the native-menu approach chosen for speed of delivery. A fully VIStk-styled context menu (custom `overrideredirect` Toplevel with themed rows, icons, hover highlights) remains possible future work — see the 1.0.0 tkinter-styles exploration.

---

### 0.6.1 Live Appearance Apply

Deferred from 0.6.0. Apply appearance settings to **already-open** windows immediately when changed in the Settings window, instead of only on next launch:

- Re-apply `appearance.font_family` / `appearance.font_size` live (walk the live widget tree / re-configure the named fonts and force a relayout).
- Wire `appearance.color_scheme` to a real styles layer once the tkinter styles system lands (see 1.0.0) — in 0.6.0 it is a stored placeholder only.

---

### 0.7.X Defaults, Navigation, and Updating Tools

- Modify default imports
- Default templates
- Enable/Disable Keyboard Navigation
- More Navigation tools
- Update tools to ensure that updating VIS will not break code
- - Should include warning if a VIS commands run but there are out of date VIS features (Host.py)
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
