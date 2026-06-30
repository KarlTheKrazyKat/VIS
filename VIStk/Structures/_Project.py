import json
import os
import re
import shutil
from VIStk.Structures._VINFO import *
from VIStk.Structures._Screen import *
from VIStk.Structures._Group import Group
from VIStk.Structures._Settings import ProjectSettings

_EDITABLE_SCREEN_ATTRS = {
    "script", "release", "icon", "desc", "tabbed",
    "single_instance", "host_menubar", "version", "current",
    "requires", "suggests", "warn_message", "docs",
}
_BOOL_ATTRS      = {"release", "tabbed", "single_instance", "host_menubar"}
_NULLABLE_ATTRS  = {"icon", "current", "warn_message", "docs"}
_VERSION_ATTRS   = {"version"}
_LIST_ATTRS      = {"requires", "suggests"}

class Project(VINFO):
    """VIS Project Object
    """
    def __init__(self):
        """Initializes or load a VIS project
        """
        super().__init__()
        self.Groups: dict[str, Group] = {Group.ALL: Group(self, Group.ALL)}
        """Mapping of group name → :class:`Group`.  Always contains the
        auto-managed ``"all"`` group, which mirrors every screen in the
        project."""
        with open(self.p_sinfo,"r") as f:
            info = json.load(f)

            for screen in list(info[self.title]["Screens"].keys()):
                scr = Screen(screen,
                             info[self.title]["Screens"][screen]["script"],
                             info[self.title]["Screens"][screen]["release"],
                             info[self.title]["Screens"][screen].get("icon"),
                             exists=True)
                self.Groups[Group.ALL].screenlist.append(scr)

            # Named groups under release_info.groups
            for gname, gdata in info[self.title].get("release_info", {}).get("groups", {}).items():
                g = Group(self, gname, gdata.get("description", ""))
                screen_entries = gdata.get("screens", [])
                # Backward-compat: legacy schema stored screens as a dict
                # ({name: {default: bool}}); we now use a flat list.
                if isinstance(screen_entries, dict):
                    screen_entries = list(screen_entries.keys())
                for sname in screen_entries:
                    scr = self.getScreen(sname)
                    if scr is not None:
                        g.screenlist.append(scr)
                self.Groups[gname] = g

            self.d_icon = info[self.title]["defaults"]["icon"]

            self.dist_location:str = info[self.title]["release_info"]["location"]
            self.hidden_imports:list[str] = info[self.title]["release_info"]["hidden_imports"]
            self.collect_packages:list[str] = info[self.title]["release_info"].get("collect_packages", [])
            self.host_script: str = info[self.title].get("host", {}).get("script", ".VIS/Host.py")
            """Filename of the Host entry-point script"""
            self.default_docs: str | None = info[self.title].get("defaults", {}).get("docs")
            """Project-level fallback documentation URL.

            Used by :meth:`resolve_docs_url` when the active screen's own
            ``Screen.docs`` is ``None``.  Passed verbatim to
            :func:`webbrowser.open`.
            """
        self.Screen: Screen = None
        """The Currently Running `Screen`"""

        self.Settings: ProjectSettings = ProjectSettings(self)
        """Per-project application settings, persisted to
        ``.VIS/settings.json``.  Use ``project.Settings.get(key, default)`` /
        ``.set(key, value)`` / ``.save()``.  See
        :class:`~VIStk.Structures._Settings.ProjectSettings`."""

    def _save_groups(self) -> None:
        """Persist every non-``"all"`` Group back to ``release_info.groups``.

        Called from :meth:`Group.add` / :meth:`Group.rem` and from
        :meth:`add` / :meth:`rem` here on Project.  Rewrites the entire
        ``release_info.groups`` dict from the current in-memory state so
        adds, removals, and membership changes all flow through one path.
        """
        with open(self.p_sinfo, "r") as f:
            info = json.load(f)
        release_info = info[self.title].setdefault("release_info", {})
        release_info["groups"] = {
            g.name: g.to_json()
            for g in self.Groups.values()
            if not g.is_all
        }
        with open(self.p_sinfo, "w") as f:
            json.dump(info, f, indent=4)

    def add(self, kind, name: str, description: str = "") -> int:
        """Create a new Group on this Project.

        Dispatched on type so future entities (e.g. Screen) can hang off
        the same verb.  Today only ``Group`` is supported.

        Returns 1 on success, 0 on failure.
        """
        if kind is Group:
            if not validName(name):
                return 0
            if name in _RESERVED_VIS_COMMANDS:
                print(f"'{name}' is a reserved VIS command.")
                return 0
            if name == Group.ALL:
                print(f"'{Group.ALL}' is reserved for the auto-managed group.")
                return 0
            if self.hasScreen(name):
                print(f"'{name}' collides with a screen name.")
                return 0
            if name in self.Groups:
                print(f"Group '{name}' already exists.")
                return 0
            self.Groups[name] = Group(self, name, description)
            self._save_groups()
            print(f"Created group '{name}'.")
            return 1
        raise TypeError(f"Project.add does not know how to create {kind!r}.")

    def rem(self, group: Group) -> int:
        """Delete an existing Group from this Project.

        ``"all"`` cannot be removed.  Returns 1 on success, 0 on failure.
        """
        if not isinstance(group, Group):
            raise TypeError(f"Project.rem expects a Group instance, got {type(group).__name__}.")
        if group.is_all:
            print(f"Cannot remove the auto-managed '{Group.ALL}' group.")
            return 0
        if group.name not in self.Groups or self.Groups[group.name] is not group:
            print(f"Group '{group.name}' is not part of this project.")
            return 0
        del self.Groups[group.name]
        self._save_groups()
        print(f"Removed group '{group.name}'.")
        return 1

    #Project Screen Methods
    def newScreen(self,screen:str) -> int:
        """Creates a new screen with some prompting

        Returns:
            0 Failed
            1 Success
        """
        #Check for valid filename  
        if not validName(screen):
            return 0
        
        with open(self.p_sinfo,"r") as f:
            info = json.load(f) #Load info

        name = self.title
        if info[name]["Screens"].get(screen) is None: #If Screen does not exist in VINFO
            while True: #ensures a valid name is used for script
                match input(f"Should python script use name {screen}.py? "):
                    case "Yes" | "yes" | "Y" | "y":
                        script = screen + ".py"
                        break
                    case _:
                        script = input("Enter the name for the script file: ").strip(".py")+".py"
                        if validName(script):
                            break

            match input("Should this screen have its own .exe?: "):
                case "Yes" | "yes" | "Y" | "y":
                    release = True
                case _:
                    release = False
            ictf =input("What is the icon for this screen (or none)?: ")
            icon = ictf.strip(".ico") if ".ICO" in ictf.upper() else None
            desc = input("Write a description for this screen: ")
            match input("Should this screen open as a tab inside the Host? "):
                case "Yes" | "yes" | "Y" | "y":
                    tabbed = True
                case _:
                    tabbed = False
            self.Groups[Group.ALL].screenlist.append(Screen(screen, script, release, icon, False, desc, tabbed))

            if self.default_screen is None:
                self.set_default_screen(screen)
                print(f"Set '{screen}' as the default screen.")

            return 1
        else:
            print(f"Information for {screen} already in project.")
            return 1

    def set_default_screen(self, screen: str) -> bool:
        """Set the default screen opened when the Host restores from the tray.

        Persists the name to ``project.json``.

        Returns:
            True if the screen exists and was set, False otherwise.
        """
        if not self.hasScreen(screen):
            return False
        self.default_screen = screen
        with open(self.p_sinfo, "r") as f:
            info = json.load(f)
        info[self.title]["defaults"]["default_screen"] = screen
        # Remove legacy top-level key if present
        info[self.title].pop("default_screen", None)
        with open(self.p_sinfo, "w") as f:
            json.dump(info, f, indent=4)
        return True

    def rename_screen(self, old_name: str, new_name: str) -> int:
        """Rename a screen: updates project.json, files, directories, and import references.

        Returns 1 on success, 0 on failure.
        """
        if not self.hasScreen(old_name):
            print(f"Screen '{old_name}' does not exist.")
            return 0
        if not validName(new_name):
            return 0
        if self.hasScreen(new_name):
            print(f"Screen '{new_name}' already exists.")
            return 0

        with open(self.p_sinfo, "r") as f:
            info = json.load(f)

        screens = info[self.title]["Screens"]
        screens[new_name] = screens.pop(old_name)

        # Rename script file if it follows the default naming convention
        old_script = screens[new_name]["script"]
        new_script = old_script
        if old_script == old_name + ".py":
            new_script = new_name + ".py"
            old_path = self.p_project + "/" + old_script
            new_path = self.p_project + "/" + new_script
            if os.path.exists(old_path):
                os.rename(old_path, new_path)
            screens[new_name]["script"] = new_script

        # Update default_screen pointer
        if info[self.title]["defaults"].get("default_screen") == old_name:
            info[self.title]["defaults"]["default_screen"] = new_name

        with open(self.p_sinfo, "w") as f:
            json.dump(info, f, indent=4)

        # Rename Screens/ directory
        old_screens_dir = self.p_screens + "/" + old_name
        new_screens_dir = self.p_screens + "/" + new_name
        if os.path.exists(old_screens_dir):
            os.rename(old_screens_dir, new_screens_dir)

        # Rename modules/ directory and hooks file inside it
        old_modules_dir = self.p_modules + "/" + old_name
        new_modules_dir = self.p_modules + "/" + new_name
        if os.path.exists(old_modules_dir):
            os.rename(old_modules_dir, new_modules_dir)
        old_hooks = new_modules_dir + "/m_" + old_name + ".py"
        new_hooks = new_modules_dir + "/m_" + new_name + ".py"
        if os.path.exists(old_hooks):
            os.rename(old_hooks, new_hooks)

        # Rewrite import references in the screen script
        new_script_path = self.p_project + "/" + new_script
        if os.path.exists(new_script_path):
            with open(new_script_path, "r") as f:
                text = f.read()
            text = re.sub(
                rf"\bScreens\.{re.escape(old_name)}\.",
                f"Screens.{new_name}.",
                text,
            )
            text = re.sub(
                rf"\bmodules\.{re.escape(old_name)}\.",
                f"modules.{new_name}.",
                text,
            )
            with open(new_script_path, "w") as f:
                f.write(text)

        # Update in-memory screenlist
        for scr in self.Groups[Group.ALL].screenlist:
            if scr.name == old_name:
                scr.name    = new_name
                scr.script  = new_script
                scr.path    = self.p_screens + "/" + new_name
                scr.m_path  = self.p_modules + "/" + new_name
                break

        if self.default_screen == old_name:
            self.default_screen = new_name

        # Re-stitch so import blocks are regenerated
        new_scr = self.getScreen(new_name)
        if new_scr:
            new_scr.stitch()

        print(f"Renamed screen '{old_name}' -> '{new_name}'.")
        return 1

    def edit_screen(self, screen_name: str, attribute: str, value: str) -> int:
        """Set any attribute in a screen's project.json subdictionary.

        Returns 1 on success, 0 on failure.
        """
        if not self.hasScreen(screen_name):
            print(f"Screen '{screen_name}' does not exist.")
            return 0
        if attribute not in _EDITABLE_SCREEN_ATTRS:
            print(
                f"Unknown attribute '{attribute}'. "
                f"Editable: {', '.join(sorted(_EDITABLE_SCREEN_ATTRS))}"
            )
            return 0

        # Extra validation for script — the file must exist
        if attribute == "script":
            candidate = self.p_project + "/" + value
            if not os.path.exists(candidate):
                print(f"Script file not found: '{candidate}'.")
                return 0

        # Type coercion
        if attribute in _BOOL_ATTRS:
            if value.lower() in ("true", "yes", "1"):
                coerced = True
            elif value.lower() in ("false", "no", "0"):
                coerced = False
            else:
                print(f"Invalid boolean value '{value}'. Use true/false/yes/no/1/0.")
                return 0
        elif attribute in _NULLABLE_ATTRS:
            coerced = None if value.lower() in ("none", "null") else value
        elif attribute in _VERSION_ATTRS:
            parts = value.split(".")
            if len(parts) != 3 or not all(p.isdigit() for p in parts):
                print(f"Invalid version '{value}'. Must be major.minor.patch format.")
                return 0
            coerced = value
        elif attribute in _LIST_ATTRS:
            if value.lower() in ("none", "null", "", "[]"):
                coerced = []
            else:
                coerced = [p.strip() for p in value.split(",") if p.strip()]
        else:
            coerced = value

        with open(self.p_sinfo, "r") as f:
            info = json.load(f)

        old_value = info[self.title]["Screens"][screen_name].get(attribute)
        info[self.title]["Screens"][screen_name][attribute] = coerced

        with open(self.p_sinfo, "w") as f:
            json.dump(info, f, indent=4)

        # Keep in-memory Screen object in sync
        scr = self.getScreen(screen_name)
        if scr is not None:
            attr_map = {
                "script":          lambda: setattr(scr, "script", coerced),
                "release":         lambda: setattr(scr, "release", coerced),
                "icon":            lambda: setattr(scr, "icon", coerced),
                "desc":            lambda: setattr(scr, "desc", coerced),
                "tabbed":          lambda: setattr(scr, "tabbed", coerced),
                "single_instance": lambda: setattr(scr, "single_instance", coerced),
                "host_menubar":    lambda: setattr(scr, "host_menubar", coerced),
                "version":         lambda: setattr(scr, "s_version", Version(coerced)),
                "current":         lambda: setattr(scr, "current", coerced),
                "requires":        lambda: setattr(scr, "requires", list(coerced)),
                "suggests":        lambda: setattr(scr, "suggests", list(coerced)),
                "warn_message":    lambda: setattr(scr, "warn_message", coerced),
                "docs":            lambda: setattr(scr, "docs", coerced),
            }
            attr_map[attribute]()

        print(f"  {screen_name}.{attribute}: {old_value!r} → {coerced!r}")
        return 1

    def hasScreen(self, screen: str) -> bool:
        """Checks if the project has a screen with the given name."""
        return self.Groups[Group.ALL].get(screen) is not None

    def getScreen(self,screen:str) -> Screen:
        """Returns a screen object by its name
        """
        return self.Groups[Group.ALL].get(screen)
        return None

    def verScreen(self,screen:str) -> Screen:
        """Verifies a screen exists and returns it

        Returns:
            screen (Screen): Verified screen
        """
        if not self.hasScreen(screen):
            self.newScreen(screen)
        scr = self.getScreen(screen)
        return scr

    def setScreen(self,screen:str) -> None:
        """Sets the currently active screen"""
        self.Screen = self.getScreen(screen)

    def load(self, screen:str, *args) -> None:
        """Loads a screen from screenlist

        Returns:
            (None): When load fails
        """
        try:
            self.getScreen(screen).load(*args)
        except AttributeError:
            return None

    def open(self, screen: str, target=None, args=None) -> None:
        """Unified navigation: opens the target screen as a new tab or window.

        When a Host is active the call is deferred via the active TabManager's
        action queue so it runs safely from the main loop, then routed to
        ``Host.open`` — which appends a new tab (for tabbed screens) or opens
        a new DetachedWindow (for standalone screens). Single-instance tabs
        are focused instead of duplicated.

        When no Host is running the call falls back to ``Screen.load()``.

        To *replace* the current pane instead of opening a new tab, call
        ``tab_manager.navigate(screen)`` directly.

        Args:
            screen: Name of the target screen.
            target: Optional TabManager whose action queue is used to defer
                the call. Defaults to the active TabManager.
            args:   Optional list of CLI-style tokens (e.g.
                ``["--won", "21930"]``) forwarded to the target screen's
                ``ArgHandler`` before its ``setup()`` runs.
        """
        from VIStk.Objects._Host import _HOST_INSTANCE
        scr = self.getScreen(screen)
        if scr is None:
            return None
        if _HOST_INSTANCE is not None:
            tm = target or _HOST_INSTANCE.active_tab_manager
            if tm is not None:
                tm._action_queue.put(lambda: _HOST_INSTANCE.open(screen, args))
            else:
                _HOST_INSTANCE.open(screen, args)
        else:
            scr.load(*(args or []))

    def reload(self) -> None:
        """Reloads the current screen

        Returns:
            (None): When load fails
        """
        try:
            self.Screen.load()
        except AttributeError:
            return None

    # ── Active-screen helpers (0.5.0) ──────────────────────────────────────

    @property
    def active_screen_name(self) -> str | None:
        """Return the ``base_name`` of the screen whose tab is focused.

        Reads the in-process ``Host`` singleton's ``active_tab_manager``
        and resolves its active ``tab_id`` back to the screen identity
        used as a key under ``project.json`` -> ``Screens``.  Returns
        ``None`` when no Host is running, no pane has focus, or the
        active pane has no open tab.
        """
        from VIStk.Objects._Host import _HOST_INSTANCE
        if _HOST_INSTANCE is None:
            return None
        tm = _HOST_INSTANCE.active_tab_manager
        if tm is None:
            return None
        active_id = getattr(tm, "active", None)
        if active_id is None:
            return None
        entry = tm._tabs.get(active_id)
        if entry is None:
            return None
        return entry.get("base_name") or entry.get("display_name")

    def sync_templates(self) -> int:
        """Refresh ``.VIS/Templates/`` from VIStk's installed templates.

        Wipes the project's current templates folder and replaces it with a
        fresh copy from VIStk.  Files that no longer exist in the source
        are removed.  Run after updating VIStk to pick up template changes
        (e.g. new default imports in ``screen.txt``).
        """
        src = VISROOT + "Templates"
        dst = self.p_templates
        if not os.path.isdir(src):
            print(f"VIStk templates not found at {src}")
            return 0
        if os.path.exists(dst):
            shutil.rmtree(dst)
        shutil.copytree(src, dst)
        print(f"Synced templates: {src} → {dst}")
        return 1

    def set_default_docs(self, url: str | None) -> int:
        """Set or clear the project-level default documentation URL.

        Writes ``defaults.docs`` in ``project.json``.  Pass ``None`` to
        clear.  Keeps the in-memory ``default_docs`` attribute in sync.
        """
        with open(self.p_sinfo, "r") as f:
            info = json.load(f)
        old = info[self.title].get("defaults", {}).get("docs")
        info[self.title].setdefault("defaults", {})["docs"] = url
        with open(self.p_sinfo, "w") as f:
            json.dump(info, f, indent=4)
        self.default_docs = url
        print(f"  project.defaults.docs: {old!r} → {url!r}")
        return 1

    def resolve_docs_url(self, screen_name: str | None = None) -> str | None:
        """Return the documentation URL for a screen, or the project default.

        Resolution order:

        1. The named screen's ``Screen.docs`` (if set)
        2. ``Project.default_docs`` (if set)
        3. ``None``

        Args:
            screen_name: Screen to resolve for.  When ``None`` (default)
                uses :attr:`active_screen_name`.
        """
        if screen_name is None:
            screen_name = self.active_screen_name
        if screen_name:
            scr = self.getScreen(screen_name)
            if scr is not None and scr.docs:
                return scr.docs
        return self.default_docs or None

    # ── Internal JSON read/write helpers ───────────────────────────────────

    def _load_info(self) -> dict:
        with open(self.p_sinfo, "r") as f:
            return json.load(f)

    def _save_info(self, info: dict) -> None:
        with open(self.p_sinfo, "w") as f:
            json.dump(info, f, indent=4)

    def required_by(self, screen_name: str) -> list[str]:
        scr = self.getScreen(screen_name)
        return list(scr.requires) if scr else []

    def suggested_by(self, screen_name: str) -> list[str]:
        scr = self.getScreen(screen_name)
        return list(scr.suggests) if scr else []

    def getInfo(self) -> str:
        """Gets the `Project` and `Screen` Info"""
        if self.Screen is None:
            return " ".join([self.title,str(self.Version)])
        else:
            return " ".join([self.title,self.Screen.name,str(self.Version)])