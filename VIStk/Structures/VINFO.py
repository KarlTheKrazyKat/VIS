import os
import json
import zipfile
import shutil
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
