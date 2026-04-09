import json
import os
import re
from VIStk.Structures._VINFO import *
from VIStk.Structures._Screen import *

_EDITABLE_SCREEN_ATTRS = {
    "script", "release", "icon", "desc", "tabbed",
    "single_instance", "version", "current",
}
_BOOL_ATTRS      = {"release", "tabbed", "single_instance"}
_NULLABLE_ATTRS  = {"icon", "current"}
_VERSION_ATTRS   = {"version"}

class Project(VINFO):
    """VIS Project Object
    """
    def __init__(self):
        """Initializes or load a VIS project
        """
        super().__init__()
        self.screenlist:list[Screen]=[]
        """A List of `Screen` Objects in the Project"""
        with open(self.p_sinfo,"r") as f:
            info = json.load(f)

            for screen in list(info[self.title]["Screens"].keys()):
                scr = Screen(screen,
                             info[self.title]["Screens"][screen]["script"],
                             info[self.title]["Screens"][screen]["release"],
                             info[self.title]["Screens"][screen].get("icon"),
                             exists=True)
                self.screenlist.append(scr)
            self.d_icon = info[self.title]["defaults"]["icon"]

            self.dist_location:str = info[self.title]["release_info"]["location"]
            self.hidden_imports:list[str] = info[self.title]["release_info"]["hidden_imports"]
            self.collect_packages:list[str] = info[self.title]["release_info"].get("collect_packages", [])
            self.host_script: str = info[self.title].get("host", {}).get("script", ".VIS/Host.py")
            """Filename of the Host entry-point script"""
        self.Screen: Screen = None
        """The Currently Running `Screen`"""

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
            self.screenlist.append(Screen(screen, script, release, icon, False, desc, tabbed))

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
        for scr in self.screenlist:
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

        print(f"Renamed screen '{old_name}' → '{new_name}'.")
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
                "version":         lambda: setattr(scr, "s_version", Version(coerced)),
                "current":         lambda: setattr(scr, "current", coerced),
            }
            attr_map[attribute]()

        print(f"  {screen_name}.{attribute}: {old_value!r} → {coerced!r}")
        return 1

    def hasScreen(self, screen: str) -> bool:
        """Checks if the project has a screen with the given name."""
        for i in self.screenlist:
            if i.name == screen:
                return True
        return False
    
    def getScreen(self,screen:str) -> Screen:
        """Returns a screen object by its name
        """
        for i in self.screenlist:
            if i.name == screen:
                return i
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

    def open(self, screen:str, stay_open:bool=False) -> None:
        """Unified navigation: routes through Host if running, else os.execl.

        When a Host is active (``VIStk.Objects._Host._HOST_INSTANCE`` is set):

        * Tabbed screen  → opens or focuses the tab inside the Host window.
        * Standalone screen, ``stay_open=False`` → Host spawns a subprocess and
          the caller closes itself.
        * Standalone screen, ``stay_open=True`` → Host spawns a subprocess; the
          caller keeps running.

        When no Host is running the call falls back to ``Screen.load()``
        (``os.execl``), preserving the existing standalone behaviour.

        Args:
            screen (str): Name of the target screen.
            stay_open (bool): Keep the current screen open when launching a
                standalone target.  Ignored when the target is tabbed.
        """
        from VIStk.Objects._Host import _HOST_INSTANCE
        scr = self.getScreen(screen)
        if scr is None:
            return None
        if _HOST_INSTANCE is not None:
            _HOST_INSTANCE.open(screen, stay_open=stay_open)
        else:
            scr.load()

    def reload(self) -> None:
        """Reloads the current screen
        
        Returns:
            (None): When load fails
        """
        try:
            self.Screen.load()
        except AttributeError:
            return None

    def getInfo(self) -> str:
        """Gets the `Project` and `Screen` Info"""
        if self.Screen is None:
            return " ".join([self.title,str(self.Version)])
        else:
            return " ".join([self.title,self.Screen.name,str(self.Version)])