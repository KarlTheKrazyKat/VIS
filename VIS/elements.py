import sys
import shutil
import os
import subprocess

project = sys.argv[1]
screen = sys.argv[2]
elements = sys.argv[3]
elements = elements.split('-')

for e in elements:
    if not os.path.exists(project+"/Screens/"+screen+"/f_"+e+".py"):
        shutil.copyfile(project+"/Templates/f_element.txt",project+"/Screens/"+screen+"/f_"+e+".py")
        subprocess.call("VIS patch " +project+" "+screen+" "+e)
    if not os.path.exists(project+"modules/"+screen+"/m_"+e+".py"):
        with open(project+"/modules/"+screen+"/m_"+e+".py", "w"): pass
    if not os.path.exists(project+screen+".py"):#cannot create elements without screen so will create screen if it doesnt exist
        shutil.copyfile(project+"/Templates/screen.txt",project+screen+".py")
        subprocess.call("VIS stitch "+project+" "+screen)
    else:
        subprocess.call("VIS stitch "+project+" "+screen)