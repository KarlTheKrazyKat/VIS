import os
def getPath():
    """Searches for .VIS folder and returns from path.cfg
    """
    sto = 0
    while True:
        try:
            step=""
            for i in range(0,sto,1): #iterate on sto to step backwards and search for project info
                step = "../" + step
            if os.path.exists(step+".VIS/"):
                return open(step+".VIS/path.cfg","r").read().replace("\\","/") #return stored path
            else:
                sto += 1
        except:
            return None #if failed return none