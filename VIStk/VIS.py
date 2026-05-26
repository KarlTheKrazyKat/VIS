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


def _read_command_aliases(cmd_file: Path) -> list[str]:
    """Cheaply extract ``__alias__`` from a ``c_*.py`` via AST (no import)."""
    import ast
    try:
        tree = ast.parse(cmd_file.read_text(encoding="utf-8"))
    except Exception:
        return []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "__alias__" for t in node.targets
        ):
            val = node.value
            if isinstance(val, ast.Constant) and isinstance(val.value, str):
                return [val.value]
            if isinstance(val, (ast.List, ast.Tuple)):
                return [e.value for e in val.elts
                        if isinstance(e, ast.Constant) and isinstance(e.value, str)]
    return []


def _resolve_token_kind(proj, token: str) -> str:
    """Mirror the Host's ``_resolve_token`` enough to classify ``token`` as a
    ``"screen"`` (GUI launch) or ``"command"`` (CLI invocation).

    A real screen name beats any alias.  A ``c_<Screen>.py`` file -- by stem
    or by ``__alias__`` -- whose stem matches a known screen counts as a
    screen (alias / intercept that ultimately opens the screen).  Anything
    else known is a command; anything unknown is also treated as a command
    so the terminal waits and can show the Host's error.
    """
    if proj.getScreen(token) is not None:
        return "screen"
    cmds_dir = Path(getPath()) / "commands"
    if cmds_dir.is_dir():
        tok_lower = token.lower()
        for cmd_file in cmds_dir.glob("c_*.py"):
            stem = cmd_file.stem[2:]  # strip leading "c_"
            if stem.lower() == tok_lower or any(
                a.lower() == tok_lower for a in _read_command_aliases(cmd_file)
            ):
                return "screen" if proj.getScreen(stem) is not None else "command"
    return "command"


def _is_cli_launch(extra) -> bool:
    """True when ``VIS <project> *extra`` is a CLI invocation (the Host prints
    and exits) rather than a GUI launch (the Host runs its event loop).

    ``--help`` / ``-h``, or a first non-flag token that doesn't resolve to a
    screen (by name, by screen alias, or by intercept), is CLI.  A bare run
    or anything that resolves to a screen is GUI.
    """
    if any(a in ("--help", "-h") for a in extra):
        return True
    try:
        proj = Project()
    except Exception:
        return False
    for a in extra:
        if not a.startswith("-"):
            return _resolve_token_kind(proj, a) != "screen"
    return False


def _run_project(extra):
    """Run the project's Host in dev with *extra* forwarded.

    A CLI invocation runs to completion with inherited stdio (output shows,
    the shell waits); a GUI launch is detached so the terminal is freed.
    """
    host_path = str(Path(getPath()) / ".VIS" / "Host.py")
    cmd = [sys.executable, host_path, *extra]
    if _is_cli_launch(extra):
        subprocess.run(cmd)
    else:
        subprocess.Popen(cmd)


def __main__():
    # `VIS <ProjectName> [args]` runs the project's Host in dev.  Forward
    # everything -- including --help -- so the project's own CLI answers,
    # instead of VIS's --help / command dispatch capturing it.  Guarded by
    # getPath() so Project() is only built inside an existing project (VINFO
    # otherwise prompts to CREATE one, e.g. for `VIS new`).
    if len(inp) >= 2 and getPath() is not None:
        try:
            _proj_title = Project().title
        except Exception:
            _proj_title = None
        if inp[1] == _proj_title:
            _run_project(inp[2:])
            return

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

        case "sync" | "Sync":
            if len(inp) < 3:
                print("Usage: VIS sync <templates>")
                return
            project = Project()
            match inp[2]:
                case "templates" | "Templates" | "t" | "T":
                    project.sync_templates()
                case _:
                    print(f"Unknown sync target: {inp[2]!r}")

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
                print("Usage: VIS group <add|remove|assign|unassign|list> ...")
                return
            project = Project()
            match inp[2]:
                case "add":
                    if len(inp) < 4:
                        print("Usage: VIS group add <group_name> [description]")
                        return
                    desc = " ".join(inp[4:]) if len(inp) > 4 else ""
                    project.add(Group, inp[3], desc)
                case "remove":
                    if len(inp) < 4:
                        print("Usage: VIS group remove <group_name>")
                        return
                    g = project.Groups.get(inp[3])
                    if g is None:
                        print(f"Group '{inp[3]}' does not exist.")
                    else:
                        project.rem(g)
                case "assign":
                    if len(inp) < 5:
                        print("Usage: VIS group assign <screen> <group>")
                        return
                    scr = project.getScreen(inp[3])
                    g = project.Groups.get(inp[4])
                    if scr is None:
                        print(f"Screen '{inp[3]}' does not exist.")
                    elif g is None:
                        print(f"Group '{inp[4]}' does not exist.")
                    elif g.is_all:
                        print(f"'{Group.ALL}' is auto-managed; cannot assign directly.")
                    else:
                        g.add(scr)
                        print(f"Assigned '{scr.name}' to group '{g.name}'.")
                case "unassign":
                    if len(inp) < 5:
                        print("Usage: VIS group unassign <screen> <group>")
                        return
                    scr = project.getScreen(inp[3])
                    g = project.Groups.get(inp[4])
                    if scr is None:
                        print(f"Screen '{inp[3]}' does not exist.")
                    elif g is None:
                        print(f"Group '{inp[4]}' does not exist.")
                    elif g.is_all:
                        print(f"'{Group.ALL}' is auto-managed; cannot unassign directly.")
                    elif scr not in g:
                        print(f"Screen '{scr.name}' is not in group '{g.name}'.")
                    else:
                        g.rem(scr)
                        print(f"Unassigned '{scr.name}' from group '{g.name}'.")
                case "list":
                    named = [g for g in project.Groups.values() if not g.is_all]
                    if not named:
                        print("No groups defined.")
                    else:
                        for g in named:
                            tag = f" — {g.description}" if g.description else ""
                            print(f"  {g.name}{tag}")
                            for sname in g.names():
                                print(f"      - {sname}")
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
                    for scr in project.Groups[Group.ALL].screenlist:
                        url = scr.docs or "(falls through to default)"
                        print(f"  {scr.name}: {url}")
                case _:
                    print(f"Unknown docs subcommand: {inp[2]!r}")

        case "release" | "Release" | "r" | "R":
            project=Project()
            flag:str=""
            type:str=""
            note:str=""
            release_groups:list[str]=[]
            release_screens:list[str]=[]
            patch_mode: bool = False
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
                            release_groups = [g.strip() for g in args[i+1].split(",") if g.strip()]
                            i += 2
                        case "Screens" | "screens":
                            if i + 1 >= len(args):
                                print(f"Missing value for {args[i]}")
                                return None
                            release_screens = [s.strip() for s in args[i+1].split(",") if s.strip()]
                            i += 2
                        case "Patch" | "patch" | "P" | "p" | "-patch" | "-Patch":
                            patch_mode = True
                            i += 1
                        case _:
                            print(f"Unknown Argument \"{args[i]}\"")
                            return None

            rel = Release(flag, type, note,
                          release_groups=release_groups or None,
                          release_screens=release_screens or None,
                          patch_mode=patch_mode)
            rel.release()
            rel.restoreAll()

        case _:
            # `VIS <ProjectName> ...` (dev project run) is handled at the top
            # of __main__; anything reaching here is an unknown command.
            print(f"Unknown command: \"{inp[1]}\". Run 'VIS --help' for usage.")
