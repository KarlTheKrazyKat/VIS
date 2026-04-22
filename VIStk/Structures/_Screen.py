import os
import json
import shutil
import re
import glob
from VIStk.Structures._VINFO import *
from tkinter import *
from pathlib import Path
import sys
import subprocess
from notifypy import Notify

class Screen(VINFO):
    """A VIS screen object
    """
    def __init__(self,name:str,script:str,release:bool=False,icon:str=None,exists:bool=True,desc:str=None,tabbed:bool=False):
        super().__init__()
        self.name:str=name
        """The Name of the `Screen`"""
        self.script:str=script
        """The Name of the python script the screen executes"""
        self.release:bool=release
        """`True` if `Screen` Should be Released as Its Own Binary"""
        self.icon:str=icon
        """The Name of the Icon for the Screen"""
        self.path = self.p_screens+"/"+self.name
        """Path to the Screen `Screens/` Folder"""
        self.m_path = self.p_modules+"/"+self.name
        """Path to the Screen `modules/` Folder"""

        if not exists:
            with open(self.p_sinfo,"r") as f:
                info = json.load(f)

            info[self.title]["Screens"][self.name] = {"script":script,"release":release}
            if not icon == None:
                info[self.title]["Screens"][self.name]["icon"] = icon

            if not desc == None:
                info[self.title]["Screens"][self.name]["desc"] = desc
            else:
                info[self.title]["Screens"][self.name]["desc"] = "A VIS Created Executable"

            info[self.title]["Screens"][self.name]["version"] = str(Version("1.0.0"))#always making first major version of screen

            info[self.title]["Screens"][self.name]["current"] = None#always making first major version of screen

            info[self.title]["Screens"][self.name]["tabbed"] = tabbed
            info[self.title]["Screens"][self.name]["single_instance"] = False

            with open(self.p_sinfo,"w") as f:
                json.dump(info,f,indent=4)

            shutil.copyfile(self.p_templates+"/screen.txt",self.p_project+"/"+script)
            os.mkdir(self.p_screens+"/"+self.name)
            os.mkdir(self.p_modules+"/"+self.name)

            with open(self.p_project+"/"+script, "r") as f:
                template = f.read()

            template = template.replace("<title>",self.name)
            if self.icon is None:
                template = template.replace("<icon>",info[self.title]["defaults"]["icon"])
            else:
                template = template.replace("<icon>",self.icon)

            with open(self.p_project+"/"+script, "w") as f:
                f.write(template)

        with open(self.p_sinfo,"r") as f:
            info = json.load(f)

        scr_data = info[self.title]["Screens"][self.name]
        self.desc = scr_data.get("desc", "")
        """Screen Description"""
        self.s_version = Version(scr_data.get("version", "0.0.0"))
        """Screen `Version`"""
        self.current = scr_data.get("current", "0.0.0")#remove later
        self.tabbed: bool = info[self.title]["Screens"][self.name].get("tabbed", False)
        """Whether this screen opens as a tab inside the Host window"""
        self.single_instance: bool = info[self.title]["Screens"][self.name].get("single_instance", False)
        """When True only one instance of this screen may be open at a time"""
        self.requires: list[str] = list(scr_data.get("requires", []))
        """Names of screens that must be installed alongside this one (hard dependency)."""
        self.suggests: list[str] = list(scr_data.get("suggests", []))
        """Names of screens recommended alongside this one (soft suggestion)."""
        self.warn_message: str | None = scr_data.get("warn_message")
        """Optional custom message shown by the installer when a dependency is unmet."""
      
    def addElement(self,element:str) -> int:
        if validName(element):
            if not os.path.exists(self.path+"/f_"+element+".py"):
                shutil.copyfile(self.p_templates+"/f_element.txt",self.path+"/f_"+element+".py")
                print(f"Created element f_{element}.py in {self.path}")
                self.patch(element)
            if not os.path.exists(self.m_path+"/m_"+element+".py"):
                with open(self.m_path+"/m_"+element+".py", "w"): pass
                print(f"Created module m_{element}.py in {self.m_path}")
            return 1
        else:
            return 0
    
    def patch(self,element:str) -> int:
        """Patches up the template after its copied
        """
        if os.path.exists(self.path+"/f_"+element+".py"):
            with open(self.path+"/f_"+element+".py","r") as f:
                text = f.read()
            text = text.replace("<frame>","f_"+element)
            with open(self.path+"/f_"+element+".py","w") as f:
                f.write(text)
            print(f"patched f_{element}.py")
            return 1
        else:
            print(f"Could not patch, element does not exist.")
            return 0
    
    @staticmethod
    def _replace_section(text: str, section_name: str, content: str) -> str:
        """Replace the body of a template section.

        Finds ``#%<section_name>`` (possibly indented) and replaces everything
        up to the next ``#%`` header with ``content``.  Content lines are
        re-indented to match the section header's indentation, so this works
        correctly for sections inside functions as well as at module level.
        """
        pattern = rf"([ \t]*#%{re.escape(section_name)}\n).*?(?=\n?[ \t]*#%|\Z)"

        def replacer(m: re.Match) -> str:
            header = m.group(1)
            indent = re.match(r"[ \t]*", header).group()
            if content and indent:
                lines = content.splitlines(keepends=True)
                indented = "".join(
                    indent + line if line.strip() else line for line in lines
                )
                return header + indented
            return header + content

        return re.sub(pattern, replacer, text, flags=re.DOTALL)

    def stitch(self) -> int:
        """Connects screen elements to a screen
        """
        with open(self.p_project+"/"+self.script,"r") as f: text = f.read()
        stitched = []

        #Elements — each f_element defines build(parent); call it inside setup()
        elements = glob.glob(self.path+'/f_*')#get all elements
        element_lines = []
        for elem_path in elements:
            module_path = elem_path.replace("\\", "/")
            module_path = module_path.replace(self.path+"/", "Screens."+self.name+".")[:-3]
            stitched.append(module_path)
            pkg, mod_name = module_path.rsplit(".", 1)
            element_lines.append(f"from {pkg} import {mod_name}")
            element_lines.append(f"{mod_name}.build(parent)")
        elements_str = ("\n".join(element_lines) + "\n") if element_lines else ""
        text = self._replace_section(text, "Screen Elements", elements_str)

        #Modules — package import pattern
        modules_pkg_init = os.path.join(self.p_project, "modules", "__init__.py")
        if not os.path.exists(modules_pkg_init):
            Path(modules_pkg_init).touch()

        modules = glob.glob(self.m_path+'/m_*')
        for m in modules:
            stitched.append(m)
        modules_str = f"from modules import {self.name}\n" if modules else ""
        text = self._replace_section(text, "Screen Modules", modules_str)

        if modules:
            mod_names = [Path(m).stem for m in sorted(modules)]
            generated_block = (
                f"_module_names = {mod_names!r}\n"
                f"\n"
                f"def __getattr__(name):\n"
                f"    if name in _module_names:\n"
                f"        import importlib\n"
                f"        mod = importlib.import_module(f'.{{name}}', __name__)\n"
                f"        globals()[name] = mod\n"
                f"        return mod\n"
                f"    raise AttributeError(f\"module {{__name__!r}} has no attribute {{name!r}}\")\n"
            )

            init_path = self.m_path + "/__init__.py"

            if os.path.exists(init_path):
                with open(init_path, "r") as f:
                    existing = f.read()
                new_init = self._replace_section(existing, "Modules (Auto-generated)", generated_block)
            else:
                new_init = (
                    "#%Modules (Auto-generated)\n"
                    f"{generated_block}\n"
                    "#%Screen Variables\n\n"
                    "#%Exports\n"
                )

            with open(init_path, "w") as f:
                f.write(new_init)

        #write out
        with open(self.p_project+"/"+self.script,"w") as f:
            f.write(text)
        print("Stitched: ")
        for i in stitched:
            print(f"\t{i} to {self.name}")

    def addMenu(self, menu: str) -> int:
        """Create a configure_menu module file for this screen.

        Creates ``modules/<screen>/m_<menu>.py`` pre-filled with a
        ``configure_menu(menubar)`` stub.

        If ``modules/<screen>/m_<screen>.py`` (the hooks module) already
        exists and does not define ``configure_menu``, a delegation function
        is appended so the new menu module is wired in automatically.  If
        ``configure_menu`` already exists in the hooks module, import
        instructions are added as comments for manual wiring.
        """
        menu_path = self.m_path + f"/m_{menu}.py"
        if os.path.exists(menu_path):
            print(f"Menu module m_{menu}.py already exists in {self.m_path}")
            return 0

        # Write the menu module with a commented cascade template
        content = (
            f"# configure_menu contributed by '{menu}' for screen '{self.name}'\n"
            f"# Fill in the items list, then set label= to whatever should appear\n"
            f"# in the Host menu bar.\n"
            f"\n"
            f"def configure_menu(tabmanager):\n"
            f"    tabmanager.add_cascade(\"{menu}\", [\n"
            f"        # {{\"label\": \"Item\",    \"command\": some_fn}},\n"
            f"        # {{\"separator\": True}},\n"
            f"        # {{\"label\": \"Submenu\", \"items\": [\n"
            f"        #     {{\"label\": \"Sub-item\", \"command\": some_fn}},\n"
            f"        # ]}},\n"
            f"    ])\n"
        )
        with open(menu_path, "w") as f:
            f.write(content)
        print(f"Created menu module m_{menu}.py in {self.m_path}")

        # Wire into the hooks module if it exists
        hooks_path = self.m_path + f"/m_{self.name}.py"
        if os.path.exists(hooks_path):
            with open(hooks_path, "r") as f:
                hooks_text = f.read()

            if "def configure_menu" not in hooks_text:
                # Safe to append a delegation function
                delegation = (
                    f"\n# Auto-wired by: VIS add screen {self.name} menu {menu}\n"
                    f"from modules.{self.name}.m_{menu} import configure_menu as _cm_{menu}\n"
                    f"\n"
                    f"def configure_menu(tabmanager):\n"
                    f"    _cm_{menu}(tabmanager)\n"
                )
                with open(hooks_path, "a") as f:
                    f.write(delegation)
                print(f"Wired configure_menu delegation into m_{self.name}.py")
            else:
                # configure_menu already exists — add import as comment
                note = (
                    f"\n# TODO: wire m_{menu} into your existing configure_menu\n"
                    f"# from modules.{self.name}.m_{menu} import configure_menu as _cm_{menu}\n"
                    f"# Then call _cm_{menu}(menubar) inside your configure_menu.\n"
                )
                with open(hooks_path, "a") as f:
                    f.write(note)
                print(
                    f"m_{self.name}.py already has configure_menu — "
                    f"added import comment for manual wiring."
                )
        return 1

    def load(self, *args):
        """Loads this screen.

        If a Host is running in-process, routes through it.  Otherwise
        spawns a Host subprocess with this screen name as the first arg.
        In a compiled (frozen) app, subprocess spawning is skipped.
        """
        from VIStk.Objects._Host import _HOST_INSTANCE
        if _HOST_INSTANCE is not None:
            _HOST_INSTANCE.open(self.name)
            return
        if getattr(sys, 'frozen', False):
            return  # compiled exe is the Host; can't spawn another
        host_path = str(Path(getPath()) / ".VIS" / "Host.py")
        subprocess.Popen([sys.executable, host_path, self.name])

    def close(self) -> bool:
        """Ask the Host to close this screen's tab.

        Closes the first open instance matching ``self.name``.  Screen code
        that has opened multiple instances and wants to close a specific
        one should hold the tab_id returned by ``TabManager.open_tab`` and
        call ``tm.close_tab(tab_id)`` directly.

        Returns ``True`` if a tab was found and closed, ``False`` otherwise.
        """
        from VIStk.Objects._Host import _HOST_INSTANCE
        if _HOST_INSTANCE is None:
            return False
        tm, tab_id = _HOST_INSTANCE._find_tab_by_base(self.name)
        if tm is not None and tab_id is not None:
            tm.close_tab(tab_id)
            return True
        return False

    def getModules(self, script:str=None) -> list[str]:
        """Gets a list of all modules in the screens folder"""
        if script is None: script = self.script
        path = self.p_project+"/"+script
        with open(path,"r") as file:
            modules=[]
            for line in file:
                splitline = line.split(" ")
                if splitline[0] == "from" or splitline[0] == "import":
                    if splitline[1].split(".")[0] in ["Screens", "modules"]:
                        modulename = splitline[1].replace("\n","")
                        modules.append(modulename)
                        modulepath = modulename.replace(".","/")+".py"
                        for i in self.getModules(modulepath):
                            if not i in modules:
                                modules.append(i)
        return modules
    
    def isolate(self):
        """Disabled releasing of other screens temporarily by settings them to None"""
        with open(self.p_sinfo,"r") as f:
            info = json.load(f)
            
        for i in info[self.title]["Screens"]:
            if i == self.name:
                if info[self.title]["Screens"][i]["release"] is True:
                    pass
                else:
                    print("Screen is not setup to release.")
            else:
                if info[self.title]["Screens"][i]["release"] is True:
                    info[self.title]["Screens"][i]["release"] = None

        with open(self.p_sinfo,"w") as f:
            json.dump(info,f,indent=4)

    def sendNotification(self, message:str):
        """Sends a notification for this application"""
        notification = Notify()
        notification.title=self.name
        notification.application_name=self.title
        notification.message=message
        notification.send()

    def __str__(self)->str:
        return self.name
    