import sys
import os
import zipfile
from importlib import metadata
from VIStk.Structures import *

inp = sys.argv

#Copied from source https://stackoverflow.com/a/75246706
def unzip_without_overwrite(src_path, dst_dir):
    with zipfile.ZipFile(src_path, "r") as zf:
        for member in zf.infolist():
            file_path = os.path.join(dst_dir, member.filename)
            if not os.path.exists(file_path):
                zf.extract(member, dst_dir)

def __main__():
    match inp[1]:
        case "-v"|"-V"|"-Version"|"-version":
            print(f"VIS Version {metadata.version('VIStk')}")
            
        case "new"|"New"|"N"|"n":#Create a new VIS project
            project = VINFO()

        case "add" | "Add" | "a" | "A":
            project = Project()
            match inp[2]:
                case "screen" | "Screen" | "s" | "S":
                    if not inp[3] == None:
                        screen = project.verScreen(inp[3])
                        if len(inp) >= 5:
                            match inp[4]:
                                case "menu" | "Menu" | "m" | "M":
                                    screen.addMenu(inp[5])
                                case "elements" | "Elements" | "e" | "E":
                                    for i in inp[5].split("-"):
                                        screen.addElement(i)
                                    screen.stitch()
                        else:
                            project.newScreen(inp[3])

        case "stitch" | "Stitch" | "s" | "S":
            project = Project()
            screen = project.getScreen(inp[2])
            if not screen == None:
                screen.stitch()
            else:
                print("Screen does not exist")

        case "release" | "Release" | "r" | "R":
            flag:str=""
            type:str=""
            note:str=""
            argstart = 2

            if inp[2] in ["Screen", "screen","S","s"]:
                argstart = 4
                screen = findScreen(inp[3])
                if not screen is None:
                    screen.isolate()

                else:
                    print(f"Cannot Locate Screen: \"{inp[3]}\"")
                    return None

            args = inp[argstart:]
            i=0
            while i < len(args):
                if "-" == args[i][0]:
                    match args[i][1:]:
                        case "Flag" | "flag" | "F" | "f":
                            flag = args[i+1]
                            i += 2
                        case "Type" | "type" | "T" | "t":
                            type = args[i+1]
                            i += 2
                        case "Note" | "note" | "N" | "n":
                            note = args[i+1]
                            i += 2
                        case _:
                            print(f"Unknown Argument \"{args[i]}\"")
                            return None

            rel = Release(flag,type,note)
            rel.release()
            rel.restoreAll()