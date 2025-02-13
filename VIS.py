import sys
import os
import zipfile
import subprocess

#Need to get current python location where VIS is installed
vl = subprocess.check_output('python -c "import os, sys; print(os.path.dirname(sys.executable))"').decode().strip("\r\n")+"\\"
print(vl)


inp = sys.argv
print("test uno")
print(inp[1])
wd = os.getcwd()
match inp[1]:
    case "new"|"New"|"N"|"n":
        #Setup project with config
        print("VIS project already initialized, overwriting path.cfg") if os.path.exists(wd+"\.VIS") else os.mkdir(wd+"\\.VIS")
        open(wd+"/.VIS/path.cfg","w").write(wd) if os.path.exists(wd+".VIS/path.cfg") else open(wd+"/.VIS/path.cfg", 'a').write(wd)
        print("Wrote path.cfg")

        #Unzip project template to project
        with zipfile.ZipFile(vl.replace("\\","/")+"\Lib\site-packages\VIS\Form.zip", "r") as form:
            form.extractall(wd)
