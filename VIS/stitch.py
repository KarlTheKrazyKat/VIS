import sys
import re
import glob

screen = sys.argv[1]
with open("L:/WOM/PYWOM/"+screen+".py","r") as f:
    text = f.read()

#Elements
pattern = r"#Screen Elements.*#Screen Grid"
replacement = glob.glob("L:/WOM/PYWOM/Screens/"+screen+'/f_*')
for i in range(0,len(replacement),1):
    replacement[i] = replacement[i].replace("\\","/")
    replacement[i] = replacement[i].replace("L:/WOM/PYWOM/Screens/"+screen+"/","Screens."+screen+".")[:-3]
#print(replacement)
replacement = "from " + " import *\nfrom ".join(replacement) + " import *\n"
#print(replacement)
text = re.sub(pattern, "#Screen Elements\n" + replacement + "\n#Screen Grid", text, flags=re.DOTALL)

#Modules
pattern = r"#Screen Modules.*#Handle Arguments"
replacement = glob.glob("L:/WOM/PYWOM/modules/"+screen+'/m_*')
for i in range(0,len(replacement),1):
    replacement[i] = replacement[i].replace("\\","/")
    replacement[i] = replacement[i].replace("L:/WOM/PYWOM/modules/"+screen+"/","modules."+screen+".")[:-3]
#print(replacement)
replacement = "from " + " import *\nfrom ".join(replacement) + " import *\n"
#print(replacement)
text = re.sub(pattern, "#Screen Modules\n" + replacement + "\n#Handle Arguments", text, flags=re.DOTALL)
#print(text)

with open("L:/WOM/PYWOM/"+screen+".py","w") as f:
    f.write(text)