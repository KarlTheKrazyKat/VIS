# VIStk Documentation

VIStk is a lightweight framework that makes building multi-screen Tkinter applications faster. It provides window and layout management, a project/screen registry, reusable widgets, and a CLI for scaffolding and releasing apps. The goal is to accelerate Tkinter development — not replace it. Standard Tkinter widgets and geometry managers work alongside VIStk objects without conflict.

---

## Table of Contents

- [Project Structure](#project-structure)
- [App Lifecycle](#app-lifecycle)
- [CLI Commands](#cli-commands)
- [Objects](#objects)
  - [Root](#root)
  - [SubRoot](#subroot)
  - [Window](#window)
  - [WindowGeometry](#windowgeometry)
  - [Layout](#layout)
  - [LayoutFrame](#layoutframe)
  - [VIMG](#vimg)
  - [ArgHandler](#arghandler)
- [Widgets](#widgets)
  - [ScrollableFrame](#scrollableframe)
  - [VISMenu](#vismenu)
  - [MenuItem](#menuitem)
  - [MenuWindow](#menuwindow)
  - [ScrollMenu](#scrollmenu)
  - [QuestionWindow](#questionwindow)
  - [WarningWindow](#warningwindow)
- [Structures](#structures)
  - [VINFO](#vinfo)
  - [Project](#project)
  - [Screen](#screen)
  - [Version](#version)
  - [Release](#release)
- [Utilities](#utilities)
  - [fUtil](#futil)
- [Templates and the #% System](#templates-and-the--system)

---

## Project Structure

A VIStk project has the following folder layout:

```text
MyProject/
├── .VIS/
│   ├── project.json        ← project registry (screens, versions, metadata)
│   ├── Templates/          ← screen and element templates used by the CLI
│   └── project.spec        ← PyInstaller spec file (generated on release)
├── Screens/
│   └── <screen>/           ← UI element files, prefixed f_ (e.g. f_header.py)
├── modules/
│   └── <screen>/           ← logic files, prefixed m_ (e.g. m_header.py)
├── Icons/                  ← .ico (Windows) or .xbm (Linux) icon files
├── Images/                 ← image assets used by VIMG
├── <screen>.py             ← main script for each screen
└── dist/                   ← compiled binaries (created on release)
```

`project.json` is the source of truth for the project. It stores screen names, script paths, icons, descriptions, version numbers, and release configuration. It is managed automatically by the CLI and by `VINFO`/`Project` — do not edit it by hand.

---

## App Lifecycle

VIStk apps do not use `mainloop()`. Screen switching works by replacing the current process with a new one via `os.execl`. Each screen is its own Python script. When the user navigates to a different screen, the current process is replaced in-place.

**Starting a screen:**

```python
from VIStk.Objects import Root

root = Root()
root.screenTitle("MyScreen")         # sets window title and tracks active screen
root.WindowGeometry.setGeometry(width=800, height=600, align="center")

# ... build your UI ...

while root.Active:
    root.update()
```

**Key rules:**

- Do not call `root.mainloop()` — this bypasses the `while` loop and traps the app.
- Do not call `root.destroy()` to quit — set `root.Active = False` instead. The loop will exit and Python will clean up naturally.
- Screen switches are handled by `Screen.load()`, which calls `os.execl` to replace the process. The current window is destroyed as part of that replacement.

---

## CLI Commands

The `VIS` command is available after installing VIStk. All commands are case-insensitive and accept single-letter abbreviations.

### Initialize a project

```text
VIS new
```

Run from the folder where you want to create the project. Creates the `.VIS/` folder, copies default templates, and prompts for project name, company, and initial version.

### Add a screen

```text
VIS add screen <screen_name>
```

Creates a new screen script from template, registers it in `project.json`, and creates the matching `Screens/<screen>/` and `modules/<screen>/` folders.

### Add elements to a screen

```text
VIS add screen <screen_name> elements <element_name>
VIS add screen <screen_name> elements <e1>-<e2>-<e3>
```

Creates `f_<element>.py` in `Screens/<screen>/` and a blank `m_<element>.py` in `modules/<screen>/`, then runs `stitch` to wire them into the screen script. Multiple elements can be created in one call by separating names with `-`.

### Stitch a screen

```text
VIS stitch <screen_name>
```

Scans `Screens/<screen>/` and `modules/<screen>/` for all `f_*` and `m_*` files and rewrites the import blocks in the screen script to include them all. This is called automatically when adding elements. Run manually if you add files without using the CLI.

### Release the project

```text
VIS release -f <suffix> -t <type> -n <note>
```

Builds a PyInstaller spec for all screens marked `release: true` in `project.json`, compiles them to native binaries, bundles required assets (Icons, Images, `.VIS`), and creates a standalone installer executable. The binaries land in `dist/`.

Options:

| Flag | Short | Description |
|------|-------|-------------|
| `-Flag` | `-f` | Suffix appended to the output folder name |
| `-Type` | `-t` | Version increment type: `Major`, `Minor`, or `Patch` |
| `-Note` | `-n` | Release note (informational) |

### Release a single screen

```text
VIS release Screen <screen_name> -f <suffix>
```

Temporarily marks all other screens as non-releasing (`isolate`), builds only the named screen, then restores the others (`restoreAll`).

### Check version

```text
VIS -v
```

Prints the installed VIStk version.

---

## Objects

Objects are the core building blocks. Import from `VIStk.Objects`.

---

### Root

`Root(Tk, Window)` — The application's main window. Wraps `Tk` with VIStk attributes.

```python
from VIStk.Objects import Root

root = Root()
```

**Attributes:**

| Attribute | Type | Description |
|-----------|------|-------------|
| `root.Active` | `bool` | Set to `False` to exit the update loop and close the app |
| `root.WindowGeometry` | `WindowGeometry` | Geometry helper attached to this window |
| `root.Layout` | `Layout` | Layout manager for this window |
| `root.Project` | `Project` | The loaded VIS project |

**Methods:**

| Method | Description |
|--------|-------------|
| `root.screenTitle(screen, title=None)` | Sets the window title and marks the active screen in `Project`. If `title` is omitted, the screen name is used. |
| `root.unload()` | Cleanly destroys all child widgets and sets `Active = False`. Wired to the window close button automatically. |
| `root.exitQueue(action, *args, **kwargs)` | Registers a function to call after the main loop exits — use for screen redirects. |
| `root.exitAct()` | Executes the registered exit action. |
| `root.fullscreen()` | Maximizes the window (zoomed, not absolute fullscreen). |
| `root.unfullscreen()` | Restores the window to normal size. |
| `root.setIcon(icon)` | Sets the window icon from `Icons/<icon>.*`. Pass the name without extension. |

**Typical pattern:**

```python
root = Root()
root.screenTitle("Home")
root.WindowGeometry.setGeometry(width=1024, height=768, align="center")
root.fullscreen()

# build UI here

while root.Active:
    root.update()
```

---

### SubRoot

`SubRoot(Toplevel, Window)` — A popup or secondary window. Wraps `Toplevel` with VIStk attributes.

```python
from VIStk.Objects import SubRoot

popup = SubRoot()
```

**Attributes:**

| Attribute | Type | Description |
|-----------|------|-------------|
| `popup.WindowGeometry` | `WindowGeometry` | Geometry helper for this window |
| `popup.Layout` | `Layout` | Layout manager for this window |
| `popup.modal` | `bool` | `True` if `modalize()` has been called |

**Methods:**

| Method | Description |
|--------|-------------|
| `popup.modalize()` | Makes the window modal — blocks input to the parent until this window is closed. Cannot be undone. |

`QuestionWindow` and `WarningWindow` are both subclasses of `SubRoot`.

---

### Window

`Window` is a mixin class inherited by both `Root` and `SubRoot`. It provides fullscreen control and icon loading. You do not instantiate it directly.

**Methods:**

| Method | Description |
|--------|-------------|
| `fullscreen(absolute=False)` | Maximizes the window. `absolute=False` uses OS maximize (zoomed); `absolute=True` uses true fullscreen with no title bar. |
| `unfullscreen(absolute=False)` | Restores window size. |
| `setIcon(icon)` | Loads `Icons/<icon>.*` as the window icon using PIL. |

---

### WindowGeometry

`WindowGeometry` handles window sizing and positioning. It is automatically attached to `Root` and `SubRoot` as `self.WindowGeometry`.

**Methods:**

#### `getGeometry(respect_size=False)`

Reads the current geometry from the window and stores it internally. If `respect_size=True`, uses the actual rendered size (`winfo_width/height`) instead of the geometry string — useful after `update()` when the window has been drawn.

#### `setGeometry(width, height, x, y, align, size_style, window_ref)`

Positions and sizes the window.

| Parameter | Type | Description |
|-----------|------|-------------|
| `width` | `int` | Width in pixels (or percentage if `size_style` is set) |
| `height` | `int` | Height in pixels (or percentage if `size_style` is set) |
| `x` | `int` | X position in pixels. Ignored if `align` is set. |
| `y` | `int` | Y position in pixels. Ignored if `align` is set. |
| `align` | `str` | Named alignment: `"center"`, `"n"`, `"ne"`, `"e"`, `"se"`, `"s"`, `"sw"`, `"w"`, `"nw"` |
| `size_style` | `str` | `"pixels"` (default), `"screen_relative"` (percentage of screen), or `"window_relative"` (percentage of `window_ref`) |
| `window_ref` | `Tk / Toplevel` | Reference window for `"window_relative"` sizing and alignment offset |

**Examples:**

```python
# Center a 800x600 window on screen
root.WindowGeometry.setGeometry(width=800, height=600, align="center")

# Center a popup on its parent window
popup.update()
popup.WindowGeometry.getGeometry(True)
popup.WindowGeometry.setGeometry(
    width=popup.winfo_width(),
    height=popup.winfo_height(),
    align="center",
    size_style="window_relative",
    window_ref=root
)
```

#### `stripGeometry(objects)`

Returns raw integer values from the current geometry string.

```python
x, y = root.WindowGeometry.stripGeometry(("x", "y"))
w, h, x, y = root.WindowGeometry.stripGeometry("all")
```

---

### Layout

`Layout` is a proportional grid system for placing frames inside a window or frame using `place()`. Rows and columns are defined as fractions that sum to 1.0.

```python
from VIStk.Objects import Layout

layout = Layout(frame)
layout.rowSize([0.1, 0.8, 0.1])      # 10% header, 80% body, 10% footer
layout.colSize([0.25, 0.75])          # 25% sidebar, 75% content
```

**Methods:**

#### `rowSize(rows)`

Sets row proportions. Each value is a float from 0.0 to 1.0. They must sum to exactly 1.0 (within floating-point tolerance).

```python
layout.rowSize([0.5, 0.5])           # two equal rows
layout.rowSize([0.1, 0.7, 0.2])      # header / body / footer
```

#### `colSize(columns)`

Sets column proportions. Same rules as `rowSize`.

```python
layout.colSize([1.0])                # single full-width column
layout.colSize([0.3, 0.7])           # sidebar / main
```

#### `cell(row, column, rowspan=None, columnspan=None)`

Returns a `dict` of `place()` kwargs for the given cell. Pass directly to `widget.place(**...)`.

```python
header = Frame(root)
header.place(**root.Layout.cell(0, 0))

# Span multiple cells
panel = Frame(root)
panel.place(**root.Layout.cell(1, 0, columnspan=2))
```

`Layout` is available on `Root` as `root.Layout` and on `SubRoot` as `popup.Layout`. It is also the basis for `LayoutFrame`.

---

### LayoutFrame

`LayoutFrame(Frame)` — A standard Tkinter `Frame` with a `Layout` object pre-attached as `self.Layout`. Use it when you need to subdivide a frame using proportional placement.

```python
from VIStk.Widgets import LayoutFrame

main_area = LayoutFrame(root)
main_area.place(**root.Layout.cell(1, 0))

main_area.Layout.colSize([0.4, 0.6])
main_area.Layout.rowSize([1.0])

left_panel = Frame(main_area)
left_panel.place(**main_area.Layout.cell(0, 0))

right_panel = Frame(main_area)
right_panel.place(**main_area.Layout.cell(0, 1))
```

---

### VIMG

`VIMG` loads and optionally auto-resizes images for Tkinter widgets using PIL. Images are loaded from the project's `Images/` folder by default.

```python
from VIStk.Objects import VIMG

img = VIMG(label_widget, "logo.png")
label_widget.configure(image=img.holder.image)
```

**Constructor:**

```python
VIMG(holder, path, absolute_path=False, size=None, fill=None)
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `holder` | `Widget` | The widget that will display the image (e.g. a `Label`) |
| `path` | `str` | Filename in `Images/`, or an absolute path if `absolute_path=True`. Extension can be omitted. |
| `absolute_path` | `bool` | If `True`, `path` is treated as a full filesystem path |
| `size` | `tuple[int,int]` | Fixed `(width, height)` in pixels. If `None`, uses the image's native size. |
| `fill` | `Widget` | If provided, the image resizes to fit this widget whenever it is resized. Binds `<Configure>` on `holder`. |

**Auto-resize example:**

```python
# Image fills a label and resizes with the window
img_label = Label(root)
img_label.place(**root.Layout.cell(0, 0))

img = VIMG(img_label, "background", fill=img_label)
```

The `fill` widget's aspect ratio determines which dimension constrains the resize — the image is scaled to fit within the widget without cropping.

---

### ArgHandler

`ArgHandler` parses command-line arguments passed to a screen script. Each flag is registered with a keyword and a callback function. Flags are passed with `--` on the command line.

```python
from VIStk.Objects import ArgHandler
import sys

handler = ArgHandler()
handler.newFlag("load", lambda args: load_record(args[0]))
handler.newFlag("mode", lambda args: set_mode(args[0]))
handler.handle(sys.argv)
```

**Command line usage:**

```text
python myscreen.py --load 1042 --mode readonly
```

**Methods:**

| Method | Description |
|--------|-------------|
| `newFlag(keyword, method)` | Registers a flag. Accepts `Keyword`, `keyword`, `K`, or `k` on the command line. Raises `KeyError` if the first letter conflicts with an existing flag. |
| `handle(args)` | Parses `sys.argv` (or any list) and calls the registered method for each `--flag` found, passing the remaining tokens as a list. |

The `ArgHandler` on the `Root.Project` is used internally by the CLI for screen loading with arguments.

---

## Widgets

Widgets extend Tkinter with compound components. Import from `VIStk.Widgets`.

---

### ScrollableFrame

`ScrollableFrame(ttk.Frame)` — A frame with a vertical scrollbar. Content is placed inside `scrollable_frame`. Mouse wheel scrolling activates when the cursor enters the frame and deactivates when it leaves.

```python
from VIStk.Widgets import ScrollableFrame

sf = ScrollableFrame(parent)
sf.pack(fill=BOTH, expand=True)

# Place content inside scrollable_frame, not sf directly
Label(sf.scrollable_frame, text="Item 1").pack()
Label(sf.scrollable_frame, text="Item 2").pack()
```

**Attributes:**

| Attribute | Type | Description |
|-----------|------|-------------|
| `sf.canvas` | `Canvas` | The underlying canvas that enables scrolling |
| `sf.scrollbar` | `ttk.Scrollbar` | The vertical scrollbar |
| `sf.scrollable_frame` | `Frame` | The inner frame — place all content here |

**Important:** All child widgets must be placed inside `sf.scrollable_frame`, not inside `sf` itself. Placing widgets directly in `sf` will put them outside the scrollable area.

---

### VISMenu

`VISMenu` builds a column of buttons from a JSON file. Each button can launch a screen by name or a script/executable by path. Keyboard shortcuts are supported via a `nav` character per item.

**JSON format:**

```json
{
    "Work Orders": {
        "text": "Work Orders",
        "path": "wo",
        "nav": "w"
    },
    "Rolodex": {
        "text": "Rolodex",
        "path": "rolo",
        "nav": "r"
    }
}
```

| Key | Description |
|-----|-------------|
| `text` | Button label |
| `path` | Screen name (matched against `project.json`), path to `.py` script, or path to `.exe` |
| `nav` | Single character — pressing this key anywhere in the window activates the button |

**Usage:**

```python
from VIStk.Widgets import VISMenu

menu = VISMenu(parent_frame, "path/to/menu.json")
```

`VISMenu` uses `grid` internally and configures the parent frame's rows and columns. Button text autosizes to fit the button. If the `path` matches a registered screen name, `Screen.load()` is called; otherwise the path is executed directly.

---

### MenuItem

`MenuItem(Button)` — A single button used by `VISMenu`. You can create `MenuItem` instances directly if you want individual menu-style buttons without a full JSON-driven menu.

```python
from VIStk.Widgets import MenuItem

btn = MenuItem(parent, path="wo", nav="w", text="Work Orders", relief="flat")
btn.grid(row=0, column=0, sticky=(N,S,E,W))
```

The button highlights blue on hover and returns to default on leave. Clicking calls `itemPath()`, which loads the screen or opens the path.

---

### MenuWindow

`MenuWindow(SubRoot)` — A floating popup window containing a `VISMenu`. Automatically centers itself over the parent window.

```python
from VIStk.Widgets import MenuWindow

menu_win = MenuWindow(root, "path/to/menu.json")
```

The window sizes itself to fit its menu content and centers on the parent. It does not need explicit geometry — `update()` and `getGeometry` are called internally.

---

### ScrollMenu

`ScrollMenu(ScrollableFrame)` — A scrollable `VISMenu`. Useful when the menu has more items than can fit on screen.

```python
from VIStk.Widgets import ScrollMenu

sm = ScrollMenu(parent, "path/to/menu.json")
sm.pack(fill=BOTH, expand=True)
```

The `VISMenu` is placed inside the `scrollable_frame` of a `ScrollableFrame`. Access the underlying menu via `sm.VISMenu`.

---

### QuestionWindow

`QuestionWindow(SubRoot)` — A configurable dialog window with a question and one or more response buttons. Centers on the parent window.

```python
from VIStk.Widgets import QuestionWindow

dlg = QuestionWindow(
    question="Save changes before closing?",
    answer="yn",
    parent=root,
    ycommand=save_and_close
)
```

**Constructor:**

```python
QuestionWindow(question, answer, parent, ycommand=None, droplist=None)
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `question` | `str` or `list[str]` | Text to display. A list creates one label per item. |
| `answer` | `str` | A string of character codes defining the buttons (see below) |
| `parent` | `Tk / Toplevel` | The window to center on |
| `ycommand` | `callable` | Function called when an affirmative button is clicked. The window is destroyed first. |
| `droplist` | `list` | Values for a dropdown (`"d"`) button |

**Answer codes:**

| Code | Button Text | Action |
|------|-------------|--------|
| `y` | Yes | Destroys window, calls `ycommand` |
| `n` | No | Destroys window |
| `r` | Return | Destroys window |
| `u` | Continue | Destroys window, calls `ycommand` |
| `b` | Back | Destroys window |
| `x` | Close | Destroys window |
| `c` | Confirm | Destroys window, calls `ycommand` |
| `d` | *(dropdown)* | `ttk.Combobox` populated from `droplist` |

**Examples:**

```python
# Yes / No
QuestionWindow("Delete this record?", "yn", root, ycommand=delete_record)

# Confirm / Back
QuestionWindow(["Are you sure?", "This cannot be undone."], "cb", root, ycommand=proceed)

# Multi-line warning with dropdown selection
QuestionWindow("Select output format:", "dx", root, droplist=["PDF", "CSV", "JSON"])
```

---

### WarningWindow

`WarningWindow(QuestionWindow)` — A modal warning dialog with a single "Continue" button.

```python
from VIStk.Widgets import WarningWindow

WarningWindow("File not found.", parent=root)
```

The window is automatically made modal (`modalize()`), blocking input to the parent until dismissed. Use for non-recoverable error messages where the user must acknowledge before continuing.

---

## Structures

Structures manage the project registry, screen lifecycle, and release pipeline. Most are used internally by the CLI and by `Root`/`Screen.load()`. Import from `VIStk.Structures`.

---

### VINFO

`VINFO` is the base class for `Project` and `Screen`. It locates the `.VIS/` folder by walking up the directory tree from the current working directory, and exposes path constants for all project directories.

You do not instantiate `VINFO` directly. It is initialized automatically when `Project()` or `Root()` is created.

**If no `.VIS/` folder exists** when `VINFO` is initialized (i.e., running `VIS new`), it creates the project structure and prompts for project name, company, and version.

**Path attributes (available on `Project` and `Screen`):**

| Attribute | Description |
|-----------|-------------|
| `p_project` | Absolute path to the project root |
| `p_vinfo` | Path to `.VIS/` |
| `p_sinfo` | Path to `.VIS/project.json` |
| `p_screens` | Path to `Screens/` |
| `p_modules` | Path to `modules/` |
| `p_templates` | Path to `.VIS/Templates/` |
| `p_icons` | Path to `Icons/` |
| `p_images` | Path to `Images/` |
| `p_vis` | Path to the installed VIStk package |
| `title` | Project name (from `project.json`) |
| `Version` | Project `Version` object |
| `company` | Company name (from `project.json`) |

**Methods:**

| Method | Description |
|--------|-------------|
| `restoreAll()` | Undoes screen isolation — restores all screens that were temporarily set to non-releasing during a single-screen release. |

---

### Project

`Project(VINFO)` — Loads the project registry from `project.json` and provides screen management. Automatically attached to `Root` as `root.Project`.

```python
from VIStk.Structures import Project

project = Project()
```

**Attributes:**

| Attribute | Type | Description |
|-----------|------|-------------|
| `project.screenlist` | `list[Screen]` | All registered screens |
| `project.Screen` | `Screen` | The currently active screen (set by `screenTitle`) |
| `project.d_icon` | `str` | Default icon name |
| `project.dist_location` | `str` | Output folder for releases |
| `project.hidden_imports` | `list[str]` | PyInstaller hidden imports |

**Methods:**

| Method | Returns | Description |
|--------|---------|-------------|
| `hasScreen(name)` | `bool` | Checks if a screen with the given name is registered |
| `getScreen(name)` | `Screen / None` | Returns the `Screen` object for the given name |
| `verScreen(name)` | `Screen` | Returns the screen if it exists, or creates it via `newScreen` |
| `setScreen(name)` | `None` | Sets `self.Screen` to the named screen |
| `load(name, *args)` | `None` | Calls `Screen.load(*args)` for the named screen |
| `reload()` | `None` | Reloads the currently active screen |
| `getInfo()` | `str` | Returns `"ProjectName ScreenName Version"` as a string |
| `newScreen(name)` | `int` | Interactively creates a new screen (CLI use) |

---

### Screen

`Screen(VINFO)` — Represents one screen in the project. Stores metadata and provides the `load()` method that switches to this screen.

**Attributes:**

| Attribute | Type | Description |
|-----------|------|-------------|
| `screen.name` | `str` | Screen name |
| `screen.script` | `str` | Python script filename (e.g. `"wo.py"`) |
| `screen.release` | `bool` | Whether this screen is compiled to its own binary |
| `screen.icon` | `str / None` | Icon name for this screen |
| `screen.desc` | `str` | Screen description |
| `screen.s_version` | `Version` | Screen-specific version number |
| `screen.path` | `str` | Absolute path to `Screens/<name>/` |
| `screen.m_path` | `str` | Absolute path to `modules/<name>/` |

**Methods:**

| Method | Description |
|--------|-------------|
| `screen.load(*args)` | Switches to this screen by replacing the current process with `os.execl`. Any `args` are passed as command-line arguments to the new script and can be read with `ArgHandler`. |
| `screen.addElement(name)` | Creates `f_<name>.py` and `m_<name>.py` from templates |
| `screen.stitch()` | Rewrites import blocks in the screen script to include all `f_*` and `m_*` files |
| `screen.getModules(script)` | Returns all `Screens.*` and `modules.*` imports found in the script, recursively |
| `screen.isolate()` | Temporarily disables release for all other screens |
| `screen.sendNotification(message)` | Sends a desktop notification for this app/screen |

**Switching screens:**

```python
# From inside a running screen
project = Project()
project.load("settings")

# With arguments
project.load("wo", "1042")          # passes "1042" to wo.py via sys.argv
```

In `wo.py`, read the argument:

```python
handler = ArgHandler()
handler.newFlag("load", lambda args: load_wo(args[0]))
handler.handle(sys.argv)
```

---

### Version

`Version` stores a semantic version number as `major.minor.patch`.

```python
from VIStk.Structures import Version

v = Version("1.3.2")
print(v)           # "1.3.2"
v.minor()
print(v)           # "1.4.0"
```

**Methods:**

| Method | Description |
|--------|-------------|
| `major()` | Increments major, resets minor and patch to 0 |
| `minor()` | Increments minor, resets patch to 0 |
| `patch()` | Increments patch |

---

### Release

`Release(Project)` — Manages the build and release pipeline. Used internally by `VIS release`. You do not normally instantiate this directly.

```python
from VIStk.Structures import Release

rel = Release(flag="beta", type="Minor")
rel.release()       # build spec, run PyInstaller, bundle assets, create installer
rel.restoreAll()    # undo any screen isolation
```

**Methods:**

| Method | Description |
|--------|-------------|
| `build()` | Generates the PyInstaller `.spec` file in `.VIS/` |
| `release()` | Runs the full pipeline: build → PyInstaller → bundle → installer |
| `clean()` | Removes build artifacts and copies Icons/Images/.VIS into the dist folder |
| `newVersion()` | Increments the project version number in `project.json` |

---

## Utilities

---

### fUtil

`fUtil` provides font creation and automatic text sizing. Import from `VIStk`.

```python
from VIStk import fUtil
```

#### `fUtil.mkfont(size, bold=False, font="default")`

Returns a font string compatible with Tkinter's `font` option.

```python
Label(parent, font=fUtil.mkfont(10))
Label(parent, font=fUtil.mkfont(14, bold=True))
```

The default font is `Arial` on Windows and `LiberationSans` on Linux.

#### `fUtil.autosize(event, relations=None, offset=None, shrink=0)`

Automatically adjusts font size so the text fills the widget as tightly as possible. Bind to `<Configure>` on the widget to keep the font size updated as the widget resizes.

```python
btn = Button(parent, text="Click Me", font=fUtil.mkfont(12))
btn.bind("<Configure>", lambda e: fUtil.autosize(e))
```

| Parameter | Description |
|-----------|-------------|
| `event` | The `<Configure>` event — provides the widget reference |
| `relations` | A list of additional widgets to resize to the same font size. The tightest-fitting widget determines the font size for all. |
| `offset` | Integer subtracted from the calculated font size |
| `shrink` | Pixel margin subtracted from the widget width before calculating |

**With relations (uniform button group):**

```python
btns = [Button(parent, text=t, font=fUtil.mkfont(12)) for t in ["First","Prev","Next","Last"]]
btns[0].bind("<Configure>", lambda e: fUtil.autosize(e, relations=btns[1:]))
```

---

## Templates and the #% System

VIStk templates use `#%` comment markers as searchable section headers. The `stitch` command uses these markers to locate and rewrite specific blocks in a screen script.

**Do not delete or rename `#%` comment lines.** They are not standard comments — they are structural anchors that VIStk searches for by text pattern.

The two critical blocks are:

```python
#%Screen Elements
from Screens.myscreen.f_header import *
from Screens.myscreen.f_body import *
#%Screen Grid

#%Screen Modules
from modules.myscreen.m_header import *
from modules.myscreen.m_body import *
#%Handle Arguments
```

`stitch` replaces everything between `#%Screen Elements` and `#%Screen Grid` with fresh imports from `Screens/<screen>/f_*.py`, and everything between `#%Screen Modules` and `#%Handle Arguments` with fresh imports from `modules/<screen>/m_*.py`.

If the VSCode VIStk extension is installed, `#%` lines are highlighted differently from regular comments.

---

## Warnings

### Do not call `root.mainloop()`

Using `mainloop()` traps the application in Tkinter's event loop and prevents the `while root.Active` pattern from working. Screen switching via `os.execl` cannot occur from inside `mainloop()`.

### Do not call `root.destroy()` to quit

Call `root.Active = False` instead. The `while` loop will exit naturally and Python will clean up the window. Calling `destroy()` directly can leave VIStk in an inconsistent state if any exit actions or redirects are queued.

### Do not edit `#%` lines

The `stitch` command and VSCode extension locate blocks by searching for these exact strings. Modifying them will break the CLI's ability to update your screen scripts automatically.
