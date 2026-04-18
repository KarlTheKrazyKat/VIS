def contextual_help(tokens: list[str]) -> None:
    """Print help for a command using the argument values already in tokens."""
    cmd = tokens[1] if len(tokens) >= 2 else ""

    # ── top-level ─────────────────────────────────────────────────────────────
    if cmd in ("", "--help", "-h"):
        _top_level()

    # ── -v / version ─────────────────────────────────────────────────────────
    elif cmd in ("-v", "-V", "-Version", "-version"):
        print("Usage:  VIS -v")
        print("Prints the installed VIStk version and exits.")

    # ── new ───────────────────────────────────────────────────────────────────
    elif cmd in ("new", "New", "N", "n"):
        print("Usage:  VIS new\n")
        print(
            "Initialises a .VIS/ folder, project.json, and Host.py in the\n"
            "current directory. Prompts for project name, company, copyright,\n"
            "and initial version. Optionally creates a first screen."
        )

    # ── add ───────────────────────────────────────────────────────────────────
    elif cmd in ("add", "Add", "a", "A"):
        name = tokens[3] if len(tokens) >= 4 else "<name>"
        kind = tokens[4].lower() if len(tokens) >= 5 else ""
        arg  = tokens[5] if len(tokens) >= 6 else None

        if kind in ("elements", "e"):
            parts = arg.split("-") if arg else ["<e1>", "<e2>"]
            files = ", ".join(f"f_{p}.py / m_{p}.py" for p in parts)
            print(f"Usage:  VIS add screen {name} elements {arg or '<e1>-<e2>-...'}\n")
            print(f"Creates {files}")
            print(f"inside Screens/{name}/ and modules/{name}/,")
            print("then stitches imports into the screen entry-point.")
        elif kind in ("menu", "m"):
            mname = arg or "<menu_name>"
            print(f"Usage:  VIS add screen {name} menu {mname}\n")
            print(f"Creates a configure_menu() stub for {name} and wires it into the screen hooks.")
        else:
            print(f"Usage:  VIS add screen {name}\n")
            print(f"Creates {name}.py, Screens/{name}/, and modules/{name}/.")
            print("\nSubcommands:")
            print(f"  VIS add screen {name} elements <e1>-<e2>   add UI element files")
            print(f"  VIS add screen {name} menu <menu_name>     add a configure_menu module")

    # ── stitch ────────────────────────────────────────────────────────────────
    elif cmd in ("stitch", "Stitch", "s", "S"):
        name = tokens[2] if len(tokens) >= 3 else "<screen_name>"
        print(f"Usage:  VIS stitch {name}\n")
        print(f"Scans Screens/{name}/ and modules/{name}/ and regenerates")
        print(f"the import block in {name}.py.")

    # ── rename ────────────────────────────────────────────────────────────────
    elif cmd in ("rename", "Rename"):
        old = tokens[2] if len(tokens) >= 3 else "<old_name>"
        new = tokens[3] if len(tokens) >= 4 else "<new_name>"
        print(f"Usage:  VIS rename {old} {new}\n")
        print(f"Renames screen '{old}' to '{new}' in project.json, directory names,")
        print("entry-point script, import references, and default_screen pointer.")

    # ── edit ──────────────────────────────────────────────────────────────────
    elif cmd in ("edit", "Edit"):
        name  = tokens[2] if len(tokens) >= 3 else "<screen_name>"
        attr  = tokens[3] if len(tokens) >= 4 else "<attribute>"
        value = tokens[4] if len(tokens) >= 5 else "<value>"
        print(f"Usage:  VIS edit {name} {attr} {value}\n")
        print("Editable attributes:")
        print("  script          path to the screen entry-point .py file")
        print("  release         true / false")
        print("  icon            icon name (no extension) or none")
        print("  desc            free-form description")
        print("  tabbed          true / false")
        print("  single_instance true / false")
        print("  version         major.minor.patch")
        print("  current         version string or none")

    # ── release ───────────────────────────────────────────────────────────────
    elif cmd in ("release", "Release", "r", "R"):
        print("Usage:  VIS release [-Flag <suffix>] [-Type Major|Minor|Patch] [-Note <text>]")
        print("        VIS release Screen <name> [-Flag <suffix>]\n")
        print(
            "Compiles the Host with Nuitka (standalone), screens as .pyd modules,\n"
            "shared packages to Shared/, bundles with Images/ and .VIS/, and\n"
            "produces a self-extracting installer in your Downloads folder.\n\n"
            "Flags (optional, any order):\n"
            "  -Flag <suffix>           suffix appended to build folder and installer name\n"
            "  -Type Major|Minor|Patch  bump project version before building\n"
            "  -Note <text>             attach a release note\n\n"
            "release Screen <name>  — isolate one screen for release"
        )

    # ── unknown ───────────────────────────────────────────────────────────────
    else:
        print(f"Unknown command '{cmd}'.")
        _top_level()


def _top_level():
    cmds = [
        ("-v",      "Show installed VIStk version"),
        ("new",     "Create a new VIS project"),
        ("add",     "Add a screen, elements, or menu"),
        ("stitch",  "Rewire imports for a screen"),
        ("rename",  "Rename a screen throughout the project"),
        ("edit",    "Set a screen attribute in project.json"),
        ("release", "Build and package as compiled executables"),
    ]
    print("VIS - VIStk project CLI\n")
    for name, desc in cmds:
        print(f"  {name:<10}  {desc}")
    print("\nAppend --help to any command for details.")
