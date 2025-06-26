import sys
import re
import glob
import project as vp

project = vp.getPath()
screen = sys.argv[1]
with open(project+"/"+screen+".py","r") as f:
    text = f.read()

#Elements
pattern = r"#Screen Elements.*#Screen Grid"
replacement = glob.glob(project+"/Screens/"+screen+'/f_*')
for i in range(0,len(replacement),1):
    replacement[i] = replacement[i].replace("\\","/")
    replacement[i] = replacement[i].replace(project+"/Screens/"+screen+"/","Screens."+screen+".")[:-3]
#print(replacement)
replacement = "from " + " import *\nfrom ".join(replacement) + " import *\n"
#print(replacement)
text = re.sub(pattern, "#Screen Elements\n" + replacement + "\n#Screen Grid", text, flags=re.DOTALL)

#Modules
pattern = r"#Screen Modules.*#Handle Arguments"
replacement = glob.glob(project+"/modules/"+screen+'/m_*')
for i in range(0,len(replacement),1):
    replacement[i] = replacement[i].replace("\\","/")
    print("stitching\t"+replacement[i].strip(project)+"\tto\t"+screen+".py")
    replacement[i] = replacement[i].replace(project+"/modules/"+screen+"/","modules."+screen+".")[:-3]
#print(replacement)
replacement = "from " + " import *\nfrom ".join(replacement) + " import *\n"
#print(replacement)
text = re.sub(pattern, "#Screen Modules\n" + replacement + "\n#Handle Arguments", text, flags=re.DOTALL)
#print(text)

with open(project+"/"+screen+".py","w") as f:
    f.write(text)
    print("stitched\t"+screen+".py\twith\tall")