import os
import json
import shutil
import re
import glob
from VIStk.Structures._VINFO import *
from tkinter import *
from pathlib import Path
import sys
import os
from notifypy import Notify

class Screen(VINFO):
    """A VIS screen object
    """
    def __init__(self,name:str,script:str,release:bool=False,icon:str=None,exists:bool=True,desc:str=None):
        super().__init__()
        self.name=name
        self.script=script
        self.release=release
        self.icon=icon
        self.path = self.p_screens+"/"+self.name
        self.m_path = self.p_modules+"/"+self.name

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

            info[self.title]["Screens"][self.name]["version"] = Version("1.0.0")#always making first major version of screen

            info[self.title]["Screens"][self.name]["current"] = None#always making first major version of screen

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

        self.desc = info[self.title]["Screens"][self.name]["desc"]
        self.s_version = Version(info[self.title]["Screens"][self.name]["version"])
        self.current = info[self.title]["Screens"][self.name]["current"]
      
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
    
    def stitch(self) -> int:
        """Connects screen elements to a screen
        """
        with open(self.p_project+"/"+self.script,"r") as f: text = f.read()
        stitched = []
        #Elements
        pattern = r"#%Screen Elements.*#%Screen Grid"

        elements = glob.glob(self.path+'/f_*')#get all elements
        for i in range(0,len(elements),1):#iterate into module format
            elements[i] = elements[i].replace("\\","/")
            elements[i] = elements[i].replace(self.path+"/","Screens."+self.name+".")[:-3]
            stitched.append(elements[i])
        #combine and change text
        elements = "from " + " import *\nfrom ".join(elements) + " import *\n"
        text = re.sub(pattern, "#%Screen Elements\n" + elements + "\n#%Screen Grid", text, flags=re.DOTALL)

        #Modules
        pattern = r"#%Screen Modules.*#%Handle Arguments"

        modules = glob.glob(self.m_path+'/m_*')#get all modules
        for i in range(0,len(modules),1):#iterate into module format
            modules[i] = modules[i].replace("\\","/")
            modules[i] = modules[i].replace(self.m_path+"/","modules."+self.name+".")[:-3]
            stitched.append(modules[i])
        #combine and change text
        modules = "from " + " import *\nfrom ".join(modules) + " import *\n"
        text = re.sub(pattern, "#%Screen Modules\n" + modules + "\n#%Handle Arguments", text, flags=re.DOTALL)

        #write out
        with open(self.p_project+"/"+self.script,"w") as f:
            f.write(text)
        print("Stitched: ")
        for i in stitched:
            print(f"\t{i} to {self.name}")

    def addMenu(self,menu:str) -> int:
        pass #will be command line menu creation tool

    def load(self):
        """Loads loads this screen"""
        os.execl(sys.executable, *(sys.executable,Path(getPath()+"/"+self.script)))

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
    