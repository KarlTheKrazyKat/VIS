import os
import subprocess
import shutil

#Need to get current python location where VIS is installed
vl = subprocess.check_output('python -c "import os, sys; print(os.path.dirname(sys.executable))"').decode().strip("\r\n")+"\\"

try:#delete spec thing
    os.remove(vl+"\\Lib\\site-packages\\VIS\\VIS.spec")
except: 
    print("Couldn't delete "+vl+"\\Lib\\site-packages\\VIS\\VIS.spec")

try:#delete build
    shutil.rmtree(vl+"\\Lib\\site-packages\\VIS\\build")
except: 
    print("Couldn't delete "+vl+"\\Lib\\site-packages\\VIS\\build")

try:#delete old .exe
    os.remove(vl+"\\Scripts\\VIS.exe")
except: 
    print("Couldn't delete "+vl+"\\Scripts\\VIS.exe")
  
try:#move VIS.exe  
    shutil.copyfile(vl+"\\Lib\\site-packages\\VIS\\dist\\VIS.exe",vl+"\\Scripts\\VIS.exe")
except: 
    print("Couldn't copy "+vl+"\\Lib\\site-packages\\VIS\\VIS.spec to "+vl+"\\Scripts\\VIS.exe")