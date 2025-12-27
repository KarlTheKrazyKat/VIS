from VIStk.Structures.project import *
from VIStk.Structures.VINFO import *
from VIStk.Structures.screen import *
import subprocess
import shutil
from os.path import exists
import time
import datetime

info = {}

class Release(Project):
    """A VIS Release object"""
    def __init__(self, flag:str="",type:str="",note:str=""):
        """Creates a Release object to release or examine a releaes of a project"""
        super().__init__()
        self.type = type
        self.flag = flag
        self.note = note

        self.location = self.dist_location.replace(".",self.p_project)
        self._internal = f"{self.location}{self.title}-{self.flag}/_internal/"

    def build(self):
        """Build project spec file for release
        """
        
        #Announce Spec Creation
        print(f"Creating project.spec for {self.name}")
        
        #Ensure spec template has hidden imports
        with open(self.p_vinfo+"/Templates/spec.txt","r+") as f:
            oldspec = f.readlines()
            newspec=""
            for line in oldspec:
                if "hiddenimports" in line:
                    line = "\thiddenimports=" + str(self.hidden_imports) + ",\n"
                newspec = newspec + line
            f.seek(0)
            f.write(newspec)
            f.truncate()

        #Load Spec & Collect
        with open(self.p_vinfo+"/Templates/spec.txt","r") as f:
            spec = f.read()
        with open(self.p_vinfo+"/Templates/collect.txt","r") as f:
            collect = f.read()
        
        #Initialize locations for builds
        spec_list = []
        name_list = []
        if os.path.exists(self.p_vinfo+"/Build"):
            shutil.rmtree(self.p_vinfo+"/Build")
        os.mkdir(self.p_vinfo+"/Build")

        #Loop and Build Screens as .txt
        for i in self.screenlist:
            if i.release:
                name_list.append(i.name)
                if not i.icon == None:
                    icon = i.icon
                else:
                    icon = self.d_icon
                if str.upper(sys.platform)=="WIN32":
                    ixt = ".ico"
                else:
                    ixt = ".xbm"
                icon = icon + ixt
                spec_list.append(spec.replace("$name$",i.name))
                spec_list[-1] = spec_list[-1].replace("$icon$",icon)
                spec_list[-1] = spec_list[-1].replace("$file$",i.script)

                #Load metadata template
                with open(self.p_templates+"/version.txt","r") as f:
                    meta = f.read()

                #Update Overall Project Version
                vers = self.version.split(".")
                major = vers[0]
                minor = vers[1]
                patch = vers[2]
                meta = meta.replace("$M$",major)
                meta = meta.replace("$m$",minor)
                meta = meta.replace("$p$",patch)

                #Update Screen Version
                vers = i.s_version.split(".")
                major = vers[0]
                minor = vers[1]
                patch = vers[2]
                meta = meta.replace("$sM$",major)
                meta = meta.replace("$sm$",minor)
                meta = meta.replace("$sp$",patch)

                #Update Company Info
                if self.company != None:
                    meta = meta.replace("$company$",self.company)
                    meta = meta.replace("$year$",str(datetime.datetime.now().year))
                else:
                    meta = meta.replace("            VALUE \"CompanyName\",      VER_COMPANYNAME_STR\n","")
                    meta = meta.replace("            VALUE \"LegalCopyright\",   VER_LEGALCOPYRIGHT_STR\n","")
                    meta = meta.replace("#define VER_LEGAL_COPYRIGHT_STR     \"Copyright © $year$ $company$\\0\"\n\n","")
                
                #Update Name & Description
                meta = meta.replace("$name$",i.name)
                meta = meta.replace("$desc$",i.desc)
                
                #Write Screen Version Metadata to .txt
                with open(self.p_vinfo+f"/Build/{i.name}.txt","w") as f:
                    f.write(meta)

                #Speclist point to correct path
                spec_list[-1] = spec_list[-1].replace("$meta$",self.p_vinfo+f"/Build/{i.name}.txt")
                spec_list.append("\n\n")

        #Create _a, _pyz, _exe and insert into Collect
        insert = ""
        for i in name_list:
            insert=insert+"\n\t"+i+"_exe,\n\t"+i+"_a.binaries,\n\t"+i+"_a.zipfiles,\n\t"+i+"_a.datas,"
        collect = collect.replace("$insert$",insert)

        #Fill Collect Name
        collect = collect.replace("$version$",self.name+"-"+self.flag) if not self.flag == "" else collect.replace("$version$",self.name)
        
        #Header for specfile
        header = "# -*- mode: python ; coding: utf-8 -*-\n\n\n"

        #Write Spec
        with open(self.p_vinfo+"/project.spec","w") as f:
            f.write(header)
            f.writelines(spec_list)
            f.write(collect)

        #Announce Completion
        print(f"Finished creating project.spec for {self.title} {self.flag if not self.flag =='' else 'current'}")#advanced version will improve this

    def clean(self):
        """Cleans up build environment to save space and appends to _internal"""
        #Announce Removal
        print("Cleaning up build environment")

        #Remove Build Folder
        if exists(self.p_vinfo+"/Build"):
            shutil.rmtree(self.p_vinfo+"/Build")

        #Announce Appending Screen Data
        print("Appending Screen Data To Environment")

        #Append Screen Data
        if self.flag == "":
            #Remove Pre-existing Folders for Icons & Images
            if exists(f"{self.location}{self.title}/Icons/"): shutil.rmtree(f"{self.location}{self.title}/Icons/")
            if exists(f"{self.location}{self.title}/Images/"): shutil.rmtree(f"{self.location}{self.title}/Images/")

            #Copy Project Folder for Icons & Images
            shutil.copytree(self.p_project+"/Icons/",f"{self.location}{self.title}/Icons/",dirs_exist_ok=True)
            shutil.copytree(self.p_project+"/Images/",f"{self.location}{self.title}/Images/",dirs_exist_ok=True)
        else:
            #Remove Pre-existing Folders for Icons & Images
            if exists(f"{self.location}{self.title}/Icons/"): shutil.rmtree(f"{self.location}{self.name}/Icons/")
            if exists(f"{self.location}{self.title}/Images/"): shutil.rmtree(f"{self.location}{self.name}/Images/")

            #Copy Project Folder for Icons & Images
            shutil.copytree(self.p_project+"/Icons/",f"{self.location}{self.title}-{self.flag}/Icons/",dirs_exist_ok=True)
            shutil.copytree(self.p_project+"/Images/",f"{self.location}{self.title}-{self.flag}/Images/",dirs_exist_ok=True)

        #Announce Completion
        print(f"\n\nReleased a new{' '+self.flag+' ' if not self.flag is None else ''}build of {self.title}!")

    def newVersion(self):
        """Updates the project version, PERMANENT, cannot be undone"""
        #Split Version for Addition
        old = str(self.version)
        vers = self.version.split(".")

        #Interate Version Number
        if self.version == "Major":
            vers[0] = str(int(vers[0])+1)
            vers[1] = str(0)
            vers[2] = str(0)
        if self.version == "Minor":
            vers[1] = str(int(vers[1])+1)
            vers[2] = str(0)
        if self.version == "Patch":
            vers[2] = str(int(vers[2])+1)
        
        #Set Version Number
        self.setVersion(f"{vers[0]}.{vers[1]}.{vers[2]}")

        #Announce Completation
        print(f"Updated Version {old}=>{self.version}")

    def release(self):
        """Releases a version of your project"""
        #Check Version
        if self.type == "":
            self.newVersion()

        #Build
        self.build()

        #Announce and Update Required Tools
        print("Updating pip...")
        subprocess.call(f"python -m pip install --upgrade pip --quiet",shell=True)

        print("Updating setuptools...")
        subprocess.call(f"python -m pip install --upgrade setuptools --quiet",shell=True)

        print("Updating pyinstaller...")
        subprocess.call(f"python -m pip install --upgrade pyinstaller --quiet",shell=True)

        #Announce and Run PyInstaller
        print(f"Running PyInstaller for {self.name}")
        subprocess.call(f"pyinstaller {self.p_vinfo}/project.spec --noconfirm --distpath {self.location} --log-level FATAL",shell=True)

        #Clean Environment
        self.clean()