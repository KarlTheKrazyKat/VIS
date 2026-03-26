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
-     : can provide screennames instead of paths
- MenuItem(Button): now menuitem is the button and text autosizes
-                 : will use screen.load() if provided with screenname

---

### 0.4.1 Screen Management

**Single-instance screens**

- New `single_instance` boolean field in each screen's `project.json` entry (default `false`)
- `Screen.__init__` reads and exposes `screen.single_instance`
- When `Host.open()` is called for a screen with `single_instance: true` that is already open anywhere (main window or any `DetachedWindow`), the existing tab is focused rather than creating a new instance; the `(2)` / `(3)` suffix logic is skipped entirely
- Set via `VIS edit <screenname> single_instance true`

**`VIS rename <screenname> <newname>`**

- Validates `newname` against the same rules as `VIS add screen` (no reserved words, valid identifier, no conflicts)
- Renames the screen's key in `project.json → Screens`
- Renames the script file on disk if the filename matches the old screen name pattern (`oldname.py` → `newname.py`); updates the `script` field accordingly
- Renames `Screens/<oldname>/` → `Screens/<newname>/`
- Renames `modules/<oldname>/` → `modules/<newname>/` and renames `m_<oldname>.py` → `m_<newname>.py` inside it
- Rewrites all `Screens.<oldname>.` and `modules.<oldname>.` import references inside the screen script
- Updates `default_screen` in `project.json` if it matches the old name
- Runs `stitch` automatically after rename so import blocks are regenerated clean
- `rename` and `Rename` added to `_RESERVED_VIS_COMMANDS`

**`VIS edit <screenname> <attribute> <value>`**

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

**`HostMenu` changes**

- `set_project_items(items, label)` — new method; appends one cascade to the project layer; calling it multiple times adds multiple project-layer cascades in order; these persist across all tab changes
- `clear_project_items()` — removes all project-layer cascades; intended for teardown, not normal use
- `set_screen_items(items, label)` — behaviour change: **accumulates** rather than replaces; calling it multiple times within a single `configure_menu` hook adds multiple screen-layer cascades side by side; still the right method for screen contributions
- `clear_screen_items()` — unchanged signature; now removes **all** accumulated screen cascades (tracked internally as a list of labels rather than a single slot)
- `_project_labels: list[str]` replaces nothing (new); `_screen_labels: list[str]` replaces the single `_screen_cascade` / `_screen_label` pair

**Usage pattern**

Project-wide items are set once in `Host.py` after `Host()` is created:

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

Screen-specific items are contributed as before via `configure_menu`:

    def configure_menu(menubar):
        menubar.set_screen_items([
            {"label": "Export PDF", "command": export_pdf},
            {"label": "Print",      "command": print_fn},
        ], label="Work Orders")

A screen that needs more than one cascade on the menu bar calls `set_screen_items` multiple times in one `configure_menu` call — all are cleared together on deactivation.

**`VIS add screen <name> menu <menuname>`**

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

**Planned**

- Auto-launch after install — optional checkbox on the completion page to launch the Host immediately after installation finishes

**Documentation updates**

- `HostMenu` section updated to describe all three layers and the accumulate behaviour of `set_screen_items`
- `configure_menu` hook documentation updated with a multi-cascade example
- `VIS add screen <name> menu <menuname>` added to the CLI reference

---

### 0.4.0 Host and Tabbed Screens

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

## Upcoming

### 0.4.3 Split Layouts, Installer Uninstaller & Install Log

Allow the Host window's content area to be divided into multiple panes, each with its own `TabBar` and `TabManager`, with a draggable sash between panes.  Two screens can then run side by side (or stacked) in a single window without spawning a `DetachedWindow`.

**Uninstaller**

- `Release.release()` generates an uninstaller executable alongside the installer
- Uninstaller reads `.VIS/install_log.json` to know exactly which files and shortcuts were created
- Removes all installed binaries, adjacent files, and desktop shortcuts
- Optionally deregisters from Windows Add/Remove Programs if the installer registered there

**Install log**

- Installer writes `.VIS/install_log.json` after a successful install — records every extracted file path, every shortcut created, the install location, and a timestamp
- The log is used by the uninstaller and by the update-in-place installer (0.4.4) to determine what is currently installed
- Quiet mode (`--Quiet`) also writes the install log

**`SplitView` widget**

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

**Drag between panes**

No changes required to `_TabBar.py` or the drag system.  Cross-bar merge already works for any two registered `TabBar` instances.  A tab dragged from one split pane into another pane's bar merges as normal.  A tab dragged outside all bars still detaches to a `DetachedWindow`.

**`Host` changes**

- `self.TabManager` replaced by `self.split_view: SplitView`; `SplitView` exposes `focused_pane` as a drop-in for the single-pane API
- `Host.open()` opens new tabs into `split_view.focused_pane` (the pane the user last interacted with)
- `Host._get_all_tab_names()` walks the full `SplitView` tree rather than a single `TabManager`
- Activate/deactivate/menu/title callbacks wired to all panes; focused pane arbitrates which tab drives `HostMenu` and the title bar
- `Host._on_tab_detach` and `Host._on_tab_popout` resolved through the originating pane's `TabManager`

**`TabBar` changes**

- `on_tab_split: callable | None` — new callback `(name: str, direction: str)`
- Right-click menu gains "Split right" and "Split down" entries that fire `on_tab_split`
- No other changes to `_TabBar.py`

**Documentation updates**

- New `SplitView` class documented with split/remove API and tree-of-panes model
- `Host` documentation updated to reflect `split_view` replacing `TabManager`
- `configure_menu` and `on_tab_activate` notes updated: these now fire per focused-pane activation, not per-window

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

### 0.4.5 Installer Polish

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

### 0.5.X VIS Widgets

Widgets that Tkinter does not provide natively. General-purpose and usable in any VIStk app.

- `Tooltip` — hover tooltip bound to any widget; Tkinter has no native tooltip
- `CollapsibleFrame` — frame with a header button that toggles content visibility
- `AutocompleteEntry` — Entry with a filtered dropdown suggestion list
- `DateEntry` — date input widget with format validation and optional calendar picker popup
- Expand custom frames
- More menu options
- Color palette feature — recolor default VIStk widgets; accessible throughout user code

---

### 0.5.X Project Upgrade Tool

`VIS upgrade` — bring an existing VIS project forward to the installed version of VIStk without touching user-written code.

**What gets updated**

Three things are replaced or patched on every upgrade; user screen scripts, `Screens/`, and `modules/` are never touched:

- **`.VIS/Host.py`** — regenerated from the current `host.txt` template; the icon name is read from `project.json` before overwriting so the setting is preserved
- **`.VIS/Templates/`** — overwritten from the VIStk install directory using `shutil.copytree`; ensures `screen.txt`, `f_element.txt`, and all widget templates match the installed version
- **`project.json` schema migration** — new keys required by newer VIStk versions are added with their default values; existing keys and user-set values are never changed or removed

**`project.json` compatibility tracking**

- A `vis_version` field is added to the `metadata` block at first upgrade (and at project creation going forward)
- The upgrade tool reads this to determine which migrations have already been applied and skips them
- On success the field is updated to the current VIStk version

**Migration registry**

Migrations live in `VIStk/Structures/_Upgrade.py` as an ordered list of `(version_string, step_fn)` pairs.  Each `step_fn(info: dict)` receives the raw `project.json` dict and adds or coerces a single field.  The runner applies all steps whose version is newer than the recorded `vis_version`.

This means upgrading across multiple releases in one step works correctly — every migration between the recorded version and the current version fires in order.

**`VIS upgrade` command**

Added to `VIS.py` as a new top-level case:

    vis upgrade

Steps in order:

1. Load `project.json` and read `metadata.vis_version` (treat missing as `"0.0.0"`)
2. Run all pending schema migrations in version order, patching `info` in memory
3. Regenerate `.VIS/Host.py` from the current template
4. Overwrite `.VIS/Templates/` from the VIStk install
5. Create any missing top-level project directories (`Screens/`, `modules/`, `Icons/`, `Images/`)
6. Write the updated `project.json` with `vis_version` set to the current VIStk version
7. Print a per-step summary — "already up to date" if nothing changed

**Dry-run flag**

    vis upgrade --dry-run

Prints what would change without writing any files.  Useful before upgrading a project that has uncommitted changes.

**Documentation updates**

- `VIS upgrade` added to the CLI reference
- `project.json` schema reference updated with `metadata.vis_version`
- Migration registry documented for contributors adding new VIStk versions

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
