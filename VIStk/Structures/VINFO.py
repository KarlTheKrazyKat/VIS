import os
import json
import zipfile
import shutil
import subprocess
import sys
import VIStk

VISROOT = VIStk.__file__.replace("__init__.pyc","").replace("__init__.py","")

#Copied from source
#https://stackoverflow.com/a/75246706
def unzip_without_overwrite(src_path, dst_dir):
    with zipfile.ZipFile(src_path, "r") as zf:
        for member in zf.infolist():
            file_path = os.path.join(dst_dir, member.filename)
            if not os.path.exists(file_path):
                zf.extract(member, dst_dir)

def getPath()->str:
    """Searches for .VIS folder
    """
    wd = os.getcwd().replace("\\","/").split("/")
    for i in range(len(wd),0,-1):
        if os.path.exists("/".join(wd[:i])+"/.VIS/"):
            return "/".join(wd[:i])
    else:
        return None

        
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
    """Overarching control structure within the /.VIS/ project folder"""
    def __init__(self):
        """Creates an overarching control stricture within the /.VIS/ project folder
        """
        if getPath() == None:
            wd = os.getcwd()
            os.mkdir(wd+"\\.VIS")

            unzip_without_overwrite(VISROOT+"Form.zip",wd)
            print(f"Copied structure to {wd}")

            shutil.copytree(VISROOT+"Templates",wd+"/.VIS/Templates",dirs_exist_ok=True)
            print(f"Loaded default templates into {wd}/.VIS/Templates/")

           
            #DO NOT MESS WITH THE TEMPLATE HEADERS

            title = input("Enter a name for the VIS project: ")
            self.title:str = title #Name of the project
            info = {}
            info[self.title] = {}
            info[self.title]["Screens"]={}
            info[self.title]["defaults"]={}
            info[self.title]["defaults"]["icon"]="VIS"#default icon
            self.d_icon = "VIS"
            info[self.title]["metadata"]={}
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
                json.dump(info,f,indent=4)
            print(f"Setup project.json for project {self.title} in {wd}/.VIS/")


        #Get VIS Root location
        self.p_vis = VIStk.__file__.replace("__init__.pyc","").replace("__init__.py","")

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
        self.version = version

        with open(self.p_sinfo,"w") as f:
            json.dump(info,f,indent=4)

    def restoreAll(self):
        """Undoes screen isolation"""
        with open(self.p_sinfo,"r") as f:
            info = json.load(f)

        for i in info[self.title]["Screens"]:
            if info[self.title]["Screens"][i]["release"] is None:
                info[self.title]["Screens"][i]["release"] = True

        with open(self.p_sinfo,"w") as f:
            json.dump(info,f,indent=4)