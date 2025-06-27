import sys
import shutil
import os
import subprocess
import project as vp

screen = sys.argv[1]
elements = sys.argv[2]
elements = elements.split('-')

project = vp.getPath()
    
for e in elements:
    if not os.path.exists(project+"/Screens/"+screen+"/f_"+e+".py"):
        shutil.copyfile(project+"/.VIS/Templates/f_element.txt",project+"/Screens/"+screen+"/f_"+e+".py")
        print("element\tf_"+e+".py\tcreated in\tScreens/"+screen+"/")
        subprocess.call("VIS patch "+project+"/Screens/"+screen+"/"+e+".py")

    if not os.path.exists(project+"/modules/"+screen+"/m_"+e+".py"):
        with open(project+"/modules/"+screen+"/m_"+e+".py", "w"): pass
        print("module\tm_"+e+".py\tcreated in\tScreens/"+screen+"/")

    if not os.path.exists(project+"/"+screen+".py"):#cannot create elements without screen so will create screen if it doesnt exist
        shutil.copyfile(project+"/.VIS/Templates/screen.txt"+project+"/"+screen+".py")
        print("screen\t"+e+".py \tcreated in\troot")

subprocess.call("VIS stitch "+screen)