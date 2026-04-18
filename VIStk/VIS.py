import sys
import os
import subprocess
import zipfile
from importlib import metadata
from pathlib import Path
from VIStk.Structures import *
from VIStk.Structures._VINFO import getPath


inp = sys.argv

#Copied from source https://stackoverflow.com/a/75246706
def unzip_without_overwrite(src_path, dst_dir):
    with zipfile.ZipFile(src_path, "r") as zf:
        for member in zf.infolist():
            file_path = os.path.join(dst_dir, member.filename)
            if not os.path.exists(file_path):
                zf.extract(member, dst_dir)

def __main__():
    if any(a in ("--help", "-h") for a in inp[1:]):
        from VIStk.Structures._Help import contextual_help
        contextual_help([a for a in inp if a not in ("--help", "-h")])
        return
    if len(inp) < 2:
        print("Usage: VIS <command> [options]. Run 'VIS --help' for details.")
        return
    match inp[1]:
        case "-v"|"-V"|"-Version"|"-version":
            print(f"VIS Version {metadata.version('VIStk')}")

        case "new"|"New"|"N"|"n":#Create a new VIS project
            VINFO()
            scr_name = input("Enter a name for the default screen (or Enter to skip): ").strip()
            if scr_name:
                Project().newScreen(scr_name)

        case "add" | "Add" | "a" | "A":
            if len(inp) < 3:
                print("Usage: VIS add <screen|...> [options]")
                return
            project = Project()
            match inp[2]:
                case "screen" | "Screen" | "s" | "S":
                    if len(inp) < 4:
                        print("Usage: VIS add screen <name> [elements|menu <arg>]")
                        return
                    screen = project.verScreen(inp[3])
                    if len(inp) >= 5:
                        match inp[4]:
                            case "menu" | "Menu" | "m" | "M":
                                if len(inp) >= 6:
                                    screen.addMenu(inp[5])
                                else:
                                    print("Usage: VIS add screen <name> menu <menuname>")
                            case "elements" | "Elements" | "e" | "E":
                                if len(inp) >= 6:
                                    for i in inp[5].split("-"):
                                        screen.addElement(i)
                                    screen.stitch()
                                else:
                                    print("Usage: VIS add screen <name> elements <elem1-elem2-...>")
                    else:
                        project.newScreen(inp[3])

        case "stitch" | "Stitch" | "s" | "S":
            if len(inp) < 3:
                print("Usage: VIS stitch <screenname>")
                return
            project = Project()
            screen = project.getScreen(inp[2])
            if screen is not None:
                screen.stitch()
            else:
                print("Screen does not exist")

        case "rename" | "Rename":
            if len(inp) < 4:
                print("Usage: VIS rename <screenname> <newname>")
            else:
                Project().rename_screen(inp[2], inp[3])

        case "edit" | "Edit":
            if len(inp) < 5:
                print("Usage: VIS edit <screenname> <attribute> <value>")
            else:
                Project().edit_screen(inp[2], inp[3], inp[4])

        case "release" | "Release" | "r" | "R":
            project=Project()
            flag:str=""
            type:str=""
            note:str=""
            argstart = 2

            if len(inp) >= 3:
                if inp[2] in ["Screen", "screen","S","s"]:
                    if len(inp) < 4:
                        print("Usage: VIS release screen <screenname> [options]")
                        return
                    argstart = 4
                    screen = project.getScreen(inp[3])
                    if screen is not None:
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
                            if i + 1 >= len(args):
                                print(f"Missing value for {args[i]}")
                                return None
                            flag = args[i+1]
                            i += 2
                        case "Type" | "type" | "T" | "t":
                            if i + 1 >= len(args):
                                print(f"Missing value for {args[i]}")
                                return None
                            type = args[i+1]
                            i += 2
                        case "Note" | "note" | "N" | "n":
                            if i + 1 >= len(args):
                                print(f"Missing value for {args[i]}")
                                return None
                            note = args[i+1]
                            i += 2
                        case _:
                            print(f"Unknown Argument \"{args[i]}\"")
                            return None

            rel = Release(flag,type,note)
            rel.release()
            rel.restoreAll()

        case _:
            project = Project()
            if inp[1] == project.title:
                # VIS <ProjectName> [ScreenName] — launch Host subprocess
                host_path = str(Path(getPath()) / ".VIS" / "Host.py")
                extra_args = inp[2:]  # screen name if provided
                subprocess.Popen([sys.executable, host_path] + extra_args)
            else:
                print(f"Unknown command: \"{inp[1]}\". Run 'VIS -v' for version info.")
