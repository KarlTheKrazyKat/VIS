import sys
from project import *
import subprocess
import json
import shutil

root = getPath()
info = {}
with open(root+"/.VIS/project.json","r") as f:
    info = json.load(f)
name = list(info.keys())[0]

def build(version:str=""):
    """Build project spec file with specific version
    """
    
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
                icon = info[name]["defaults"]["icon"]#should probably package VIS with a default icon?
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

def clean(version:str=""):
    try:
        shutil.rmtree(root+"/.VIS/build/")
        print(f"\n\nReleased new{version}build of {name}!")
    except:pass

version = sys.argv[1]
match version:
    case "a":
        build("alpha")
        subprocess.call("pyinstaller project.spec --noconfirm --distpath "+root+"/dist/")
        clean(" alpha ")
    case "b":
        build("beta")
        subprocess.call("pyinstaller project.spec --noconfirm --distpath "+root+"/dist/")
        clean(" beta ")
    case "c":
        build()
        subprocess.call("pyinstaller project.spec --noconfirm --distpath "+root+"/dist/")
        clean()
    case _:
        inp = input(f"Release Project Version {version}?")
        match inp:
            case "y" | "Y" | "yes" | "Yes":
                build(version)
                subprocess.call("pyinstaller project.spec --noconfirm --distpath "+root+"/dist/")
                clean(f" {version} ")
            case _:
                print(f"Could not release Project Version {version}")