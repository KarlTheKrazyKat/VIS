import sys
import os
import zipfile
import subprocess
import shutil
import project as vp
from importlib import metadata
import json

#Need to get current python location where VIS is installed
vl = subprocess.check_output('python -c "import os, sys; print(os.path.dirname(sys.executable))"').decode().strip("\r\n")+"\\Lib\\site-packages\\VIS\\"
#print(vl)

inp = sys.argv
#print("entered ",inp[1]," as ",inp)
try:
    (wd := os.getcwd()) if inp[1] in ["new","New","N","n"] else (wd := vp.getPath())
except:
    print(f"VIS Version {metadata.version("VIS")}")
    sys.exit()

#Copied from source
#https://stackoverflow.com/a/75246706
def unzip_without_overwrite(src_path, dst_dir):
    with zipfile.ZipFile(src_path, "r") as zf:
        for member in zf.infolist():
            file_path = os.path.join(dst_dir, member.filename)
            if not os.path.exists(file_path):
                zf.extract(member, dst_dir)
def __main__():
    match inp[1]:
        case "new"|"New"|"N"|"n":#Create a new VIS project
            if vp.getPath() == None:
                os.mkdir(wd+"\\.VIS")
                open(wd+"/.VIS/path.cfg","w").write(wd) if os.path.exists(wd+"/.VIS/path.cfg") else open(wd+"/.VIS/path.cfg", 'a').write(wd)
                print(f"Created path.cfg as {vp.getPath()}")
                unzip_without_overwrite(vl.replace("\\","/")+"Form.zip",wd)#Unzip project template to project
                shutil.copytree(vl+"Templates",wd+".VIS/Templates",dirs_exist_ok=True)#copy templates to project
                #DO NOT MESS WITH THE TEMPLATE HEADERS
                title = input("Enter a name for the VIS project:")
                info = {}
                info[title] = {}
                info[title]["Screens"]={}
                info[title]["defaults"]={}
                info[title]["defaults"]["icon"]="VIS"#default icon
                os.mkdir(wd+"\\.VIS\\project.json")
                with open(wd+"/.VIS/project.json","w") as f:
                    json.dump(info,f,indent=4)
            else:
                print(f"VIS project already initialized with path {vp.getPath()}") 

        case "add" | "Add" | "a" | "A":
            match inp[2]:
                case "screen" | "Screen" | "s" | "S":
                    screen = inp[3] #File & directory creation for VIS structure
                    print("Screens/"+screen+"\t exists") if os.path.exists(wd+"/Screens/"+screen) else os.mkdir(wd+"/Screens/"+screen)
                    print("modules/"+screen+"\t exists") if os.path.exists(wd+"/modules/"+screen) else os.mkdir(wd+"/modules/"+screen)
                    print(screen+".py\t\t exists") if os.path.exists(wd+screen+".py") else shutil.copyfile(wd+"/.VIS/Templates/screen.txt",wd+"/"+screen+".py") 
                    
                    with open(wd+"/.VIS/project.json","r") as f:
                        info = json.load(f)
                    name = list(info.keys())[0]
                    if info[name]["Screens"].get(screen) == None:
                        sc_name = input("What is the name of this screen?: ")
                        info[name]["Screens"][sc_name] ={}
                        info[name]["Screens"][sc_name]["script"] = screen+".py"
                        match input("Should this screen have its own .exe?: "):
                            case "Yes" | "yes" | "Y" | "y":
                                info[name]["Screens"][sc_name]["release"] = "TRUE"
                            case _:
                                info[name]["Screens"][sc_name]["release"] = "FALSE"
                        ictf =input("What is the icon for this screen (or none)?: ")
                        if ".ICO" in ictf.upper():
                            info[name]["Screens"][sc_name]["icon"] = ictf.strip(".ico")
                        with open(wd+"/.VIS/project.json","w") as f:
                            json.dump(info,f,indent=4)
                    #somewhere in this process we can attempt to replace "Placeholder Title" and the root.iconbitmap
                        

                    if len(inp) >= 5:
                        match inp[4]:
                            case "menu" | "Menu" | "m" | "M":
                                print("Add screen menu")
                            case "elements" | "Elements" | "e" | "E":
                                subprocess.call("python " + vl.replace("\\","/")+"/elements.py "+ screen + " " + inp[5])
                    else:
                        print("Add Screen")

        case "patch" | "Patch" | "p" | "P":
            subprocess.call("python " + vl.replace("\\","/")+"/patch.py " + inp[2])

        case "stitch" | "Stitch" | "s" | "S":
            subprocess.call("python " + vl.replace("\\","/")+"/stitch.py "+ inp[2])

        case "release" | "Release" | "r" | "R":
            subprocess.call("python " + vl.replace("\\","/")+"/release.py " + inp[2])
