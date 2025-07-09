import sys
import os
import zipfile
from VIS.project import *
from importlib import metadata
from VIS.release import newRelease

inp = sys.argv
print(f"VIS Version {metadata.version("VIStk")}")


#Copied from source https://stackoverflow.com/a/75246706
def unzip_without_overwrite(src_path, dst_dir):
    with zipfile.ZipFile(src_path, "r") as zf:
        for member in zf.infolist():
            file_path = os.path.join(dst_dir, member.filename)
            if not os.path.exists(file_path):
                zf.extract(member, dst_dir)
def __main__():
    match inp[1]:
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
            if len(inp) == 4:
                newRelease(inp[2],inp[3])
            else:
                newRelease(inp[2])
