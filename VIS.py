import sys
import os
import zipfile
import subprocess
import shutil

#Need to get current python location where VIS is installed
vl = subprocess.check_output('python -c "import os, sys; print(os.path.dirname(sys.executable))"').decode().strip("\r\n")+"\\"
#print(vl)


inp = sys.argv
#print("entered ",inp[1]," as ",inp)
wd = os.getcwd()

#Copied from source
#https://stackoverflow.com/a/75246706
def unzip_without_overwrite(src_path, dst_dir):
    with zipfile.ZipFile(src_path, "r") as zf:
        for member in zf.infolist():
            file_path = os.path.join(dst_dir, member.filename)
            if not os.path.exists(file_path):
                zf.extract(member, dst_dir)

match inp[1]:
    case "new"|"New"|"N"|"n":#Create a new VIS project
        #Setup project with config
        print("VIS project already initialized, overwriting path.cfg") if os.path.exists(wd+"\.VIS") else os.mkdir(wd+"\\.VIS")
        open(wd+"/.VIS/path.cfg","w").write(wd) if os.path.exists(wd+"/.VIS/path.cfg") else open(wd+"/.VIS/path.cfg", 'a').write(wd)
        print("Wrote path.cfg")

        #Unzip project template to project
        unzip_without_overwrite(vl.replace("\\","/")+"\Lib\site-packages\VIS\Form.zip",wd)
        shutil.copytree(vl+"Lib\site-packages\VIS\Templates",wd+"/Templates",dirs_exist_ok=True)
        #DO NOT MESS WITH THE TEMPLATES

    case "add" | "Add" | "a" | "A":
        match inp[2]:
            case "screen" | "Screen" | "s" | "S":

                screen = inp[3]
                print("elements container ",screen," exists") if os.path.exists(wd+"/Screens/"+screen) else os.mkdir(wd+"/Screens/"+screen)
                print("module ",screen," exists") if os.path.exists(wd+"/modules/"+screen) else os.mkdir(wd+"/modules/"+screen)
                print("Screen ",screen," exists") if os.path.exists(wd+screen+".py") else shutil.copyfile(wd+"/Templates/screen.txt",wd+"/"+screen+".py") 
                
                if len(inp) >= 5:
                    match inp[4]:
                        case "menu" | "Menu" | "m" | "M":
                            print("Add screen menu")
                        case "elements" | "Elements" | "e" | "E":
                            subprocess.call("python " + vl.replace("\\","/")+"Lib/site-packages/VIS/VIS/elements.py "+ wd + " "+ screen + " " + inp[5])
                else:
                    print("Add Screen")
    case "patch" | "Patch" | "p" | "P":
        subprocess.call("python " + vl.replace("\\","/")+"Lib/site-packages/VIS/VIS/patch.py " + inp[2].replace("\\","/")+"/Screens/"+inp[3]+"/"+inp[4]+".py")
    case "stitch" | "Stitch" | "s" | "S":
        print("python " + vl.replace("\\","/")+"Lib/site-packages/VIS/VIS/stitch.py "+ inp[2] + " " +inp[3])
        subprocess.call("python "  + vl.replace("\\","/")+"Lib/site-packages/VIS/VIS/stitch.py "+ inp[2] + " " +inp[3])