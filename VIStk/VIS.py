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

        case "group" | "Group":
            if len(inp) < 3:
                print("Usage: VIS group <add|remove|assign|unassign|default|list> ...")
                return
            project = Project()
            match inp[2]:
                case "add":
                    if len(inp) < 4:
                        print("Usage: VIS group add <group_name> [description]")
                        return
                    desc = " ".join(inp[4:]) if len(inp) > 4 else ""
                    project.add_group(inp[3], desc)
                case "remove":
                    if len(inp) < 4:
                        print("Usage: VIS group remove <group_name>")
                        return
                    project.remove_group(inp[3])
                case "assign":
                    if len(inp) < 5:
                        print("Usage: VIS group assign <screen> <group> [true|false]")
                        return
                    default = True
                    if len(inp) >= 6:
                        default = inp[5].lower() in ("true", "yes", "1")
                    project.assign_to_group(inp[3], inp[4], default)
                case "unassign":
                    if len(inp) < 4:
                        print("Usage: VIS group unassign <screen>")
                        return
                    project.unassign_from_group(inp[3])
                case "default":
                    if len(inp) < 5:
                        print("Usage: VIS group default <screen> <true|false>")
                        return
                    d = inp[4].lower() in ("true", "yes", "1")
                    project.set_group_default(inp[3], d)
                case "list":
                    groups = project.groups()
                    if not groups:
                        print("No groups defined.")
                    else:
                        for gname, gdata in groups.items():
                            desc = gdata.get("description", "")
                            print(f"  {gname}" + (f" — {desc}" if desc else ""))
                            for sname, sdata in gdata.get("screens", {}).items():
                                d_mark = "" if sdata.get("default", True) else "  [off by default]"
                                print(f"      - {sname}{d_mark}")
                case _:
                    print(f"Unknown group subcommand: {inp[2]!r}")

        case "docs" | "Docs":
            # VIS docs set <screen|--default> <url>
            # VIS docs clear <screen|--default>
            # VIS docs list
            if len(inp) < 3:
                print("Usage: VIS docs <set|clear|list> ...")
                return
            project = Project()
            match inp[2]:
                case "set":
                    if len(inp) < 5:
                        print("Usage: VIS docs set <screen_name|--default> <url>")
                        return
                    target, url = inp[3], inp[4]
                    if target in ("--default", "--Default", "-d", "-D"):
                        project.set_default_docs(url)
                    else:
                        project.edit_screen(target, "docs", url)
                case "clear":
                    if len(inp) < 4:
                        print("Usage: VIS docs clear <screen_name|--default>")
                        return
                    target = inp[3]
                    if target in ("--default", "--Default", "-d", "-D"):
                        project.set_default_docs(None)
                    else:
                        project.edit_screen(target, "docs", "null")
                case "list":
                    default = project.default_docs or "(none)"
                    print(f"  --default: {default}")
                    for scr in project.screenlist:
                        url = scr.docs or "(falls through to default)"
                        print(f"  {scr.name}: {url}")
                case _:
                    print(f"Unknown docs subcommand: {inp[2]!r}")

        case "release" | "Release" | "r" | "R":
            project=Project()
            flag:str=""
            type:str=""
            note:str=""
            subset_groups:list[str]=[]
            subset_screens:list[str]=[]
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
                        case "Groups" | "groups" | "G" | "g":
                            if i + 1 >= len(args):
                                print(f"Missing value for {args[i]}")
                                return None
                            subset_groups = [g.strip() for g in args[i+1].split(",") if g.strip()]
                            i += 2
                        case "Screens" | "screens":
                            if i + 1 >= len(args):
                                print(f"Missing value for {args[i]}")
                                return None
                            subset_screens = [s.strip() for s in args[i+1].split(",") if s.strip()]
                            i += 2
                        case _:
                            print(f"Unknown Argument \"{args[i]}\"")
                            return None

            rel = Release(flag, type, note,
                          subset_groups=subset_groups or None,
                          subset_screens=subset_screens or None)
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
