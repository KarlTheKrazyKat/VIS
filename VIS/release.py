from VIS.project import *
from VIS.VINFO import *
from VIS.screen import *
import subprocess
import shutil
from os.path import exists
import time
import datetime

info = {}

class Release():
    """A VIS Release object"""
    def __init__(self, project :Project, version:str="",type:str="",note:str=""):
        """Creates a Release object to release or examine a releaes of a project"""
        self.project = project
        self.version = version
        self.type = type
        self.note = note

    def build(self):
        """Build project spec file for release
        """
        
        print(f"Creating project.spec for {self.project.name}")

        with open(self.project.p_vinfo+"/Templates/spec.txt","r") as f:
            spec = f.read()
        with open(self.project.p_vinfo+"/Templates/collect.txt","r") as f:
            collect = f.read()
        
        spec_list = []
        name_list = []
        os.mkdir(self.project.p_vinfo+"/Build")
        for i in self.project.screenlist:
            if i.release:
                name_list.append(i.name)
                if not i.icon == None:
                    icon = i.icon
                else:
                    icon = self.project.d_icon
                spec_list.append(spec.replace("$name$",i.name))
                spec_list[len(spec_list)-1] = spec_list[len(spec_list)-1].replace("$icon$",icon)
                spec_list[len(spec_list)-1] = spec_list[len(spec_list)-1].replace("$file$",i.script)

                #build metadata
                with open(self.project.p_templates+"/version.txt","r") as f:
                    meta = f.read()

                #Update Overall Project Version
                vers = self.project.version.split(".")
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

                if self.project.company != None:
                    meta = meta.replace("$company$",self.project.company)
                    meta = meta.replace("$year$",str(datetime.datetime.now().year))
                else:
                    meta = meta.replace("            VALUE \"CompanyName\",      VER_COMPANYNAME_STR\n","")
                    meta = meta.replace("            VALUE \"LegalCopyright\",   VER_LEGALCOPYRIGHT_STR\n","")
                    meta = meta.replace("#define VER_LEGAL_COPYRIGHT_STR     \"Copyright © $year$ $company$\\0\"\n\n","")
                meta = meta.replace("$name$",i.name)
                meta = meta.replace("$desc$",i.desc)
                
                with open(self.project.p_vinfo+f"/Build/{i.name}.txt","w") as f:
                    f.write(meta)
                spec_list[len(spec_list)-1] = spec_list[len(spec_list)-1].replace("$meta$",self.project.p_vinfo+f"/Build/{i.name}.txt")
                spec_list.append("\n\n")

        insert = ""
        for i in name_list:
            insert=insert+"\n\t"+i+"_exe,\n\t"+i+"_a.binaries,\n\t"+i+"_a.zipfiles,\n\t"+i+"_a.datas,"
        collect = collect.replace("$insert$",insert)
        collect = collect.replace("$version$",self.project.name+"-"+self.version) if not self.version == "" else collect.replace("$version$",self.project.name)
        
        header = "# -*- mode: python ; coding: utf-8 -*-\n\n\n"

        with open(self.project.p_vinfo+"/project.spec","w") as f:
            f.write(header)
        with open(self.project.p_vinfo+"/project.spec","a") as f:
            f.writelines(spec_list)
            f.write(collect)

        print(f"Finished creating project.spec for {self.project.title} {self.version if not self.version =="" else "current"}")#advanced version will improve this

    def clean(self):
        """Cleans up build environment to save space
        """
        print("Cleaning up build environment")
        shutil.rmtree(self.project.p_vinfo+"/Build")
        print("Appending Screen Data To Environment")
        if self.version == " ":
            if exists(f"{self.project.p_project}/dist/{self.project.title}/Icons/"): shutil.rmtree(f"{self.project.p_project}/dist/{self.project.title}/Icons/")
            if exists(f"{self.project.p_project}/dist/{self.project.title}/Images/"): shutil.rmtree(f"{self.project.p_project}/dist/{self.project.title}/Images/")
            shutil.copytree(self.project.p_project+"/Icons/",f"{self.project.p_project}/dist/{self.project.title}/Icons/",dirs_exist_ok=True)
            shutil.copytree(self.project.p_project+"/Images/",f"{self.project.p_project}/dist/{self.project.title}/Images/",dirs_exist_ok=True)
        else:
            if exists(f"{self.project.p_project}/dist/{self.project.title}/Icons/"): shutil.rmtree(f"{self.project.p_project}/dist/{self.project.name}/Icons/")
            if exists(f"{self.project.p_project}/dist/{self.project.title}/Images/"): shutil.rmtree(f"{self.project.p_project}/dist/{self.project.name}/Images/")
            shutil.copytree(self.project.p_project+"/Icons/",f"{self.project.p_project}/dist/{self.project.title}-{self.version.strip(" ")}/Icons/",dirs_exist_ok=True)
            shutil.copytree(self.project.p_project+"/Images/",f"{self.project.p_project}/dist/{self.project.title}-{self.version.strip(" ")}/Images/",dirs_exist_ok=True)
        print(f"\n\nReleased new{self.version}build of {self.project.title}!")

    def newVersion(self):
        """Updates the project version, PERMANENT, cannot be undone
        """
        old = str(self.project.version)
        vers = self.project.version.split(".")
        if self.version == "Major":
            vers[0] = str(int(vers[0])+1)
            vers[1] = str(0)
            vers[2] = str(0)
        if self.version == "Minor":
            vers[1] = str(int(vers[1])+1)
            vers[2] = str(0)
        if self.version == "Patch":
            vers[2] = str(int(vers[2])+1)

        self.project.setVersion(f"{vers[0]}.{vers[1]}.{vers[2]}")
        self.project = VINFO()
        print(f"Updated Version {old}=>{self.project.version}")

    def makeRelease(self):
        """Releases a version of your project
        """
        match self.version:
            case "a":
                self.build("alpha")
                subprocess.call(f"pyinstaller {self.project.p_vinfo}/project.spec --noconfirm --distpath {self.project.p_project}/dist/ --log-level FATAL")
                self.clean(" alpha ")
            case "b":
                self.build("beta")
                subprocess.call(f"pyinstaller {self.project.p_vinfo}/project.spec --noconfirm --distpath {self.project.p_project}/dist/ --log-level FATAL")
                self.clean(" beta ")
            case "c":
                self.newVersion(type)
                self.build()
                subprocess.call(f"pyinstaller {self.project.p_vinfo}/project.spec --noconfirm --distpath {self.project.p_project}/dist/ --log-level FATAL")
                self.clean()
            case "sync":
                self.build("alpha")
                subprocess.call(f"pyinstaller {self.project.p_vinfo}/project.spec --noconfirm --distpath {self.project.p_project}/dist/ --log-level FATAL")
                self.clean(" alpha ")
                self.build("beta")
                subprocess.call(f"pyinstaller {self.project.p_vinfo}/project.spec --noconfirm --distpath {self.project.p_project}/dist/ --log-level FATAL")
                self.clean(" beta ")
                self.build()
                subprocess.call(f"pyinstaller {self.project.p_vinfo}/project.spec --noconfirm --distpath {self.project.p_project}/dist/ --log-level FATAL")
                self.clean()
                print("\t- alpha\n\t- beta\n\t- current")
            case _:
                print(f"Could not release Project Version {self.version}")