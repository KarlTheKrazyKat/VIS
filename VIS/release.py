import sys
from project import *
import subprocess
import json

root = getPath()
print(root)

def setVersion(vers:str=""):
    """Sets name in project.spec
    """
    spec = ""
    with open(root+"/.VIS/project.spec","r") as f:
        spec = f.read()
    setup = spec.split("COLLECT")[0]
    collect = spec.split("COLLECT")[1]
    name = collect.split("name=")[1]
    collect = collect.split("name=")[0]
    with open(root+"/.VIS/project.json","r") as p: #get project name from json file
        info = json.load(p)
        name = f"name='{list(info.keys())[0]+vers}')"#
    collect = collect + name
    spec = setup + "COLLECT" + collect
    with open(root+"/.VIS/project.spec","w") as f:
        f.write(spec)

version = sys.argv[1]
match version:
    case "a":
        setVersion("-alpha")
        subprocess.call("pyinstaller project.spec --noconfirm --distpath "+root+"/dist/")
    case "b":
        setVersion("-beta")
        subprocess.call("pyinstaller project.spec --noconfirm --distpath "+root+"/dist/")
    case "c":
        setVersion()
        subprocess.call("pyinstaller project.spec --noconfirm --distpath "+root+"/dist/")
    case _:
        inp = input(f"Release Project Version {version}?")
        match inp:
            case "y" | "Y" | "yes" | "Yes":
                setVersion("-"+version)
                subprocess.call("pyinstaller project.spec --noconfirm --distpath "+root+"/dist/")
            case _:
                print(f"Could not release Project Version {version}")