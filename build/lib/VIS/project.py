import os

def getPath():

    Project=False
    sto = 0
    while Project==False:
        step=""
        for i in range(0,sto,1):
            step = "../" + step
        #print(step+".VIS/")
        if os.path.exists(step+".VIS/"):
            #print("found project at ", step+".VIS/")
            project = open(step+".VIS/path.cfg","r").read().replace("\\","/")
            #print(project)
            Project = True
        else:
            sto += 1

    return project