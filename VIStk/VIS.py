import sys
import os
import subprocess
import tempfile
import time
import zipfile
from importlib import metadata
from VIStk.Structures import *


def _start_host_and_wait(project, timeout: float = 5.0) -> bool:
    """Spawn the project Host as a subprocess and wait for IPC to become ready.

    Returns True if the Host's port file appears within *timeout* seconds,
    False otherwise.  Returns False immediately in compiled (frozen) apps
    where subprocess spawning is not possible.
    """
    if getattr(sys, 'frozen', False):
        return False
    host_path = project.p_project + "/" + project.host_script
    subprocess.Popen([sys.executable, host_path])
    safe = project.title.replace(" ", "_")
    port_file = os.path.join(tempfile.gettempdir(), f"{safe}_vis_host.port")
    deadline = time.time() + timeout
    while time.time() < deadline:
        if os.path.exists(port_file):
            time.sleep(0.15)  # Give the socket a moment to finish binding
            return True
        time.sleep(0.05)
    return False

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

        case "stop" | "Stop":
            info = VINFO()
            if send_to_host(info.title, "__VIS_QUIT__"):
                print(f"Stopped Host for project '{info.title}'.")
            else:
                print(f"No Host is running for project '{info.title}'.")

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
                if len(inp) >= 3:
                    # VIS <ProjectName> <ScreenName> — open a screen via Host,
                    # starting the Host first if it is not already running.
                    screen = project.getScreen(inp[2])
                    if screen is not None:
                        if not send_to_host(project.title, screen.name):
                            if _start_host_and_wait(project):
                                send_to_host(project.title, screen.name)
                            else:
                                print(f"Failed to start Host for '{project.title}'.")
                    else:
                        names = ", ".join(s.name for s in project.screenlist)
                        print(f"Unknown screen: \"{inp[2]}\". Available: {names}")
                else:
                    # VIS <ProjectName> — start Host if needed, then open default screen.
                    safe = project.title.replace(" ", "_")
                    port_file = os.path.join(tempfile.gettempdir(),
                                             f"{safe}_vis_host.port")
                    if not os.path.exists(port_file):
                        if not _start_host_and_wait(project):
                            print(f"Failed to start Host for '{project.title}'.")
                    if project.default_screen:
                        send_to_host(project.title, project.default_screen)
            else:
                print(f"Unknown command: \"{inp[1]}\". Run 'VIS -v' for version info.")