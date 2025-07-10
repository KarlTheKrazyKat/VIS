import os
import json
import zipfile
import shutil
import re
import glob
import subprocess

#Copied from source
#https://stackoverflow.com/a/75246706
def unzip_without_overwrite(src_path, dst_dir):
    with zipfile.ZipFile(src_path, "r") as zf:
        for member in zf.infolist():
            file_path = os.path.join(dst_dir, member.filename)
            if not os.path.exists(file_path):
                zf.extract(member, dst_dir)

def getPath():
    """Searches for .VIS folder and returns from path.cfg
    """
    sto = 0
    while True:
        try:
            step=""
            for i in range(0,sto,1): #iterate on sto to step backwards and search for project info
                step = "../" + step
            if os.path.exists(step+".VIS/"):
                return open(step+".VIS/path.cfg","r").read().replace("\\","/") #return stored path
            else:
                if os.path.exists(step):
                    sto += 1
                else:
                    return None #return none if cant escape more
        except:
            return None #if failed return none
        
def validName(name:str):
    """Checks if provided path is a valid filename
    """
    if " " in name:
        print("Cannot have spaces in file name.")
        return False
    if "/" in name or "\\" in name:
        print("Cannot have filepath deliminator in file name.")
        return False
    if "<" in name or ">" in name or ":" in name or '"' in name or "|" in name or "?" in name or "*" in name:
        print('Invlaid ASCII characters for windows file creation, please remove all <>:"|?* from file name.')
        return False
    if name.split(".")[0] in ["CON","PRN","AUX","NUL","COM1","COM2","COM3","COM4","COM5","COM6","COM7","COM8","COM9","LPT1","LPT2","LPT3","LPT4","LPT5","LPT6","LPT7","LPT8","LPT9"]:
        print(f"Filename {name} reserved by OS.")
        return False
    if "" == name:
        print("Must provide a name for file.")
        return False
    else:
        return True


class VINFO():
    """Overarching control structure within the /.VIS/ folder
    """
    def __init__(self):
        if getPath() == None:
            wd = os.getcwd()
            os.mkdir(wd+"\\.VIS")
            open(wd+"/.VIS/path.cfg","w").write(wd) if os.path.exists(wd+"/.VIS/path.cfg") else open(wd+"/.VIS/path.cfg", 'a').write(wd)
            print(f"Stored project path in path.cfg as {wd} in {wd}/.VIS/path.cfg")

            unzip_without_overwrite("./Form.zip",wd)
            print(f"Copied structure to {wd}")

            shutil.copytree("./Templates",wd+"/.VIS/Templates",dirs_exist_ok=True)
            print(f"Loaded default templates into {wd}/.VIS/Templates/")

           
            #DO NOT MESS WITH THE TEMPLATE HEADERS

            title = input("Enter a name for the VIS project: ")
            self.title = title
            info = {}
            info[self.title] = {}
            info[self.title]["Screens"]={}
            info[self.title]["defaults"]={}
            info[self.title]["defaults"]["icon"]="VIS"#default icon
            self.d_icon = "VIS"
            self[self.title]["metadata"]={}
            comp = input("What company is this for(or none)? ")
            if not comp in ["none","None"]:
                info[self.title]["metadata"]["company"] = comp
                self.company = comp
            else:
                info[self.title]["metadata"]["company"] = None
                self.company = None

            version = input("What is the initial version for the project (0.0.1 default): ")
            vers = version.split(".")
            if len(vers)==3:
                if vers[0].isnumeric() and vers[1].isnumeric() and vers[2].isnumeric():
                    self.version = version
                else:
                    self.version = "0.0.1"
            else:
                self.version = "0.0.1"
            info[self.title]["metadata"]["version"] = self.version

            with open(wd+"/.VIS/project.json","w") as f:
                f.write("{}")
                json.dump(info,f,indent=4)
            print(f"Setup project.json for project {self.title} in {wd}/.VIS/")


        #Need to get current python location where VIS is installed
        self.p_vis = subprocess.check_output('python -c "import os, sys; print(os.path.dirname(sys.executable))"').decode().strip("\r\n")+"\\Lib\\site-packages\\VIS\\"


        self.p_project = getPath()
        self.p_vinfo = self.p_project + "/.VIS"
        self.p_sinfo = self.p_vinfo + "/project.json"
        with open(self.p_sinfo,"r") as f: 
            info = json.load(f)
            self.title = list(info.keys())[0]
            self.version = info[self.title]["metadata"]["version"]
            self.company = info[self.title]["metadata"]["company"]
            
        self.screenlist = []
        self.p_screens = self.p_project +"/Screens"
        self.p_modules = self.p_project +"/modules"
        self.p_templates = self.p_vinfo + "/Templates"
        self.p_icons = self.p_project + "/Icons"
        self.p_images = self.p_project + "/Images"
        
    def setVersion(self,version:str):
        """Sets a new project version
        """
        with open(self.p_sinfo,"r") as f: 
            info = json.load(f)

        info[self.title]["metadata"]["version"] = version

        with open(self.p_sinfo,"w") as f:
            json.dump(info,f,indent=4)


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

            info[self.title]["Screens"][self.name]["version"] = "1.0.0"#always making first major version of screen

            info[self.title]["Screens"][self.name]["current"] = None#always making first major version of screen

            with open(self.p_sinfo,"w") as f:
                json.dump(info,f,indent=4)

            shutil.copyfile(self.p_templates+"/screen.txt",self.p_project+"/"+script)
            os.mkdir(self.p_screens+"/"+self.name)
            os.mkdir(self.p_modules+"/"+self.name)

        with open(self.p_sinfo,"r") as f:
                info = json.load(f)
        self.desc = info[self.title]["Screens"][self.name]["desc"]
        self.s_version = info[self.title]["Screens"][self.name]["version"]
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
        
    def addMenu(self,menu:str) -> int:
        pass #will be command line menu creation tool

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
        pattern = r"#Screen Elements.*#Screen Grid"

        elements = glob.glob(self.path+'/f_*')#get all elements
        for i in range(0,len(elements),1):#iterate into module format
            elements[i] = elements[i].replace("\\","/")
            elements[i] = elements[i].replace(self.path+"/","Screens."+self.name+".")[:-3]
            stitched.append(elements[i])
        #combine and change text
        elements = "from " + " import *\nfrom ".join(elements) + " import *\n"
        text = re.sub(pattern, "#Screen Elements\n" + elements + "\n#Screen Grid", text, flags=re.DOTALL)

        #Modules
        pattern = r"#Screen Modules.*#Handle Arguments"

        modules = glob.glob(self.m_path+'/m_*')#get all modules
        for i in range(0,len(modules),1):#iterate into module format
            modules[i] = modules[i].replace("\\","/")
            modules[i] = modules[i].replace(self.m_path+"/","modules."+self.name+".")[:-3]
            stitched.append(modules[i])
        #combine and change text
        modules = "from " + " import *\nfrom ".join(modules) + " import *\n"
        text = re.sub(pattern, "#Screen Modules\n" + modules + "\n#Handle Arguments", text, flags=re.DOTALL)

        #write out
        with open(self.p_project+"/"+self.script,"w") as f:
            f.write(text)
        print("Stitched: ")
        for i in stitched:
            print(f"\t{i} to {self.name}")

    def syncVersion(self) -> int:
        """Syncs the version stored in sinfo with the version in memory
        """
        with open(self.p_sinfo,"r") as f:
            info = json.load(f)
        info[self.title]["Screens"][self.name]["current"] = self.current
        with open(self.p_sinfo,"w") as f:
            json.dump(info,f)
        return 1

    def crntVersion(self) -> int:
        """Checks if the version needs to be synced and returns 1 if its synced
        """
        if not self.s_version == self.current:
            self.current = self.version
            self.syncVersion()
            return 1
        else:
            return 0


class Project(VINFO):
    """VIS Project Object
    """
    def __init__(self):
        """Initializes or load a VIS project
        """
        super().__init__()
        with open(self.p_sinfo,"r") as f:
            info = json.load(f)
            self.name = list(info.keys())[0]

            for screen in list(info[self.name]["Screens"].keys()):
                scr = Screen(screen,
                             info[self.name]["Screens"][screen]["script"],
                             info[self.name]["Screens"][screen]["release"],
                             info[self.name]["Screens"][screen].get("icon"),
                             exists=True)
                self.screenlist.append(scr)
            self.d_icon = info[self.name]["defaults"]["icon"]
    
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
        if info[name]["Screens"].get(screen) == None: #If Screen does not exist in VINFO
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
            self.screenlist.append(Screen(screen,script,release,icon,False,desc))

            return 1
        else:
            print(f"Information for {screen} already in project.")
            return 1

    def hasScreen(self,screen:str) -> bool:
        """Checks if the project has the correct screen
        """
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

