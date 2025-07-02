import sys
from project import *
import subprocess
import json
import shutil
from os.path import exists

root = getPath()
info = {}
with open(root+"/.VIS/project.json","r") as f:
    info = json.load(f)
name = list(info.keys())[0]

def build(version:str=""):
    """Build project spec file with specific version
    """
    
    print(f"Creating project.spec for {name}")

    with open(root+"/.VIS/Templates/spec.txt","r") as f:
        spec = f.read()
    with open(root+"/.VIS/Templates/collect.txt","r") as f:
        collect = f.read()
    
    spec_list = []
    name_list = []
    
    for i in info[name]["Screens"].keys():
        if info[name]["Screens"][i]["release"] == "TRUE":
            name_list.append(i)
            file = info[name]["Screens"][i]["script"]
            #icon = "du"
            if not info[name]["Screens"][i].get("icon") == None:
                icon = info[name]["Screens"][i]["icon"]
            else:
                icon = info[name]["defaults"]["icon"]
            spec_list.append(spec.replace("$name$",i))
            spec_list[len(spec_list)-1] = spec_list[len(spec_list)-1].replace("$icon$",icon)
            spec_list[len(spec_list)-1] = spec_list[len(spec_list)-1].replace("$file$",file)
            spec_list.append("\n\n")

    insert = ""
    for i in name_list:
        insert=insert+"\n\t"+i+"_exe,\n\t"+i+"_a.binaries,\n\t"+i+"_a.zipfiles,\n\t"+i+"_a.datas,"
    collect = collect.replace("$insert$",insert)
    collect = collect.replace("$version$",name+"-"+version) if not version == "" else collect.replace("$version$",name)
    
    header = "# -*- mode: python ; coding: utf-8 -*-\n\n\n"

    with open(root+"/.VIS/project.spec","w") as f:
        f.write(header)
    with open(root+"/.VIS/project.spec","a") as f:
        f.writelines(spec_list)
        f.write(collect)

    print(f"Setup project.spec for {name} {version if not version =="" else "current"}")#advanced version will improve this

def clean(version:str=" "):
    """Cleans up build environment to save space
    """
    print("Cleaning up build environment")
    if version == "":
        if exists(f"{root}/dist/{name}/Icons/"): shutil.rmtree(f"{root}/dist/{name}/Icons/")
        if exists(f"{root}/dist/{name}/Images/"): shutil.rmtree(f"{root}/dist/{name}/Images/")
        shutil.copytree(root+"/Icons/",f"{root}/dist/{name}/Icons/",dirs_exist_ok=True)
        shutil.copytree(root+"/Images/",f"{root}/dist/{name}/Images/",dirs_exist_ok=True)
    else:
        if exists(f"{root}/dist/{name}/Icons/"): shutil.rmtree(f"{root}/dist/{name}/Icons/")
        if exists(f"{root}/dist/{name}/Images/"): shutil.rmtree(f"{root}/dist/{name}/Images/")
        shutil.copytree(root+"/Icons/",f"{root}/dist/{name}-{version.strip(" ")}/Icons/",dirs_exist_ok=True)
        shutil.copytree(root+"/Images/",f"{root}/dist/{name}-{version.strip(" ")}/Images/",dirs_exist_ok=True)
    print(f"\n\nReleased new{version}build of {name}!")

version = sys.argv[1]
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
        inp = input(f"Release Project Version {version}?")
        match inp:
            case "y" | "Y" | "yes" | "Yes":
                build(version)
                subprocess.call(f"pyinstaller {root}/.VIS/project.spec --noconfirm --distpath {root}/dist/ --log-level FATAL")
                clean(f" {version} ")
            case _:
                print(f"Could not release Project Version {version}")