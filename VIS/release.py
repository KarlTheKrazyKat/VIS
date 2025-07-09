from VIS.project import *
import subprocess
import shutil
from os.path import exists
import time

root = getPath()
info = {}
project = Project()


def build(version:str=""):
    """Build project spec file with specific version
    """
    
    print(f"Creating project.spec for {project.name}")

    with open(root+"/.VIS/Templates/spec.txt","r") as f:
        spec = f.read()
    with open(root+"/.VIS/Templates/collect.txt","r") as f:
        collect = f.read()
    
    spec_list = []
    name_list = []
    
    for i in project.screenlist:
        if i.release:
            name_list.append(i.name)
            if not i.icon == None:
                icon = i.icon
            else:
                icon = project.d_icon
            spec_list.append(spec.replace("$name$",i.name))
            spec_list[len(spec_list)-1] = spec_list[len(spec_list)-1].replace("$icon$",icon)
            spec_list[len(spec_list)-1] = spec_list[len(spec_list)-1].replace("$file$",i.script)

            #build meta
            with open(project.p_templates+"/meta.txt","r") as f:
                meta = f.read()
            meta = meta.replace("$version$",project.version)
            if project.company != None:
                meta = meta.replace("$company$",project.company)
            else:
                meta = meta.replace("\tcompany='$company$',\n","")
            meta = meta.replace("$name$",project.title)
            meta = meta.replace("$description$",i.desc)
            print(meta)
            spec_list[len(spec_list)-1] = spec_list[len(spec_list)-1].replace("$meta$",meta)
            spec_list.append("\n\n")

    insert = ""
    for i in name_list:
        insert=insert+"\n\t"+i+"_exe,\n\t"+i+"_a.binaries,\n\t"+i+"_a.zipfiles,\n\t"+i+"_a.datas,"
    collect = collect.replace("$insert$",insert)
    collect = collect.replace("$version$",project.name+"-"+version) if not version == "" else collect.replace("$version$",project.name)
    
    header = "# -*- mode: python ; coding: utf-8 -*-\n\n\n"

    with open(root+"/.VIS/project.spec","w") as f:
        f.write(header)
    with open(root+"/.VIS/project.spec","a") as f:
        f.writelines(spec_list)
        f.write(collect)

    print(f"Finished creating project.spec for {project.name} {version if not version =="" else "current"}")#advanced version will improve this

def clean(version:str=" "):
    """Cleans up build environment to save space
    """
    print("Cleaning up build environment")
    if version == " ":
        if exists(f"{root}/dist/{project.name}/Icons/"): shutil.rmtree(f"{root}/dist/{project.name}/Icons/")
        if exists(f"{root}/dist/{project.name}/Images/"): shutil.rmtree(f"{root}/dist/{project.name}/Images/")
        shutil.copytree(root+"/Icons/",f"{root}/dist/{project.name}/Icons/",dirs_exist_ok=True)
        shutil.copytree(root+"/Images/",f"{root}/dist/{project.name}/Images/",dirs_exist_ok=True)
    else:
        if exists(f"{root}/dist/{project.name}/Icons/"): shutil.rmtree(f"{root}/dist/{project.name}/Icons/")
        if exists(f"{root}/dist/{project.name}/Images/"): shutil.rmtree(f"{root}/dist/{project.name}/Images/")
        shutil.copytree(root+"/Icons/",f"{root}/dist/{project.name}-{version.strip(" ")}/Icons/",dirs_exist_ok=True)
        shutil.copytree(root+"/Images/",f"{root}/dist/{project.name}-{version.strip(" ")}/Images/",dirs_exist_ok=True)
    print(f"\n\nReleased new{version}build of {project.name}!")

def newVersion(version:str):
    """Updates the project version, permanent, cannot be undone
    """
    project = VINFO()
    old = str(project.version)
    vers = project.version.split(".")
    if version == "Major":
        vers[0] = str(int(vers[0])+1)
        vers[1] = str(0)
        vers[2] = str(0)
    if version == "Minor":
        vers[1] = str(int(vers[1])+1)
        vers[2] = str(0)
    if version == "Patch":
        vers[2] = str(int(vers[2])+1)

    project.setVersion(f"{vers[0]}.{vers[1]}.{vers[2]}")
    project = VINFO()
    print(f"Updated Version {old}=>{project.version}")

def newRelease(version,type:str="Patch"):
    """Releases a version of your project
    """
    match version:
        case "a":
            build("alpha")
            subprocess.call(f"pyinstaller {root}/.VIS/project.spec --noconfirm --distpath {root}/dist/ --log-level FATAL")
            clean(" alpha ")
        case "b":
            build("beta")
            subprocess.call(f"pyinstaller {root}/.VIS/project.spec --noconfirm --distpath {root}/dist/ --log-level FATAL")
            clean(" beta ")
        case "c":
            newVersion(type)
            build()
            subprocess.call(f"pyinstaller {root}/.VIS/project.spec --noconfirm --distpath {root}/dist/ --log-level FATAL")
            clean()
        case "sync":
            build("alpha")
            subprocess.call(f"pyinstaller {root}/.VIS/project.spec --noconfirm --distpath {root}/dist/ --log-level FATAL")
            clean(" alpha ")
            build("beta")
            subprocess.call(f"pyinstaller {root}/.VIS/project.spec --noconfirm --distpath {root}/dist/ --log-level FATAL")
            clean(" beta ")
            build()
            subprocess.call(f"pyinstaller {root}/.VIS/project.spec --noconfirm --distpath {root}/dist/ --log-level FATAL")
            clean()
            print("\t- alpha\n\t- beta\n\t- current")
        case _:
            print(f"Could not release Project Version {version}")