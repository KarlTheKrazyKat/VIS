import json
from VIStk.Structures.VINFO import *
from VIStk.Structures.screen import *
from VIStk.Objects._Root import *

class Project(VINFO):
    """VIS Project Object
    """
    def __init__(self):
        """Initializes or load a VIS project
        """
        super().__init__()
        with open(self.p_sinfo,"r") as f:
            info = json.load(f)
            self.name = list(info.keys())[0]

            for screen in list(info[self.name]["Screens"].keys()):
                scr = Screen(screen,
                             info[self.name]["Screens"][screen]["script"],
                             info[self.name]["Screens"][screen]["release"],
                             info[self.name]["Screens"][screen].get("icon"),
                             exists=True)
                self.screenlist.append(scr)
            self.d_icon = info[self.name]["defaults"]["icon"]

            self.dist_location:str = info[self.name]["release_info"]["location"]
            self.hidden_imports:list[str] = info[self.name]["release_info"]["hidden_imports"]
    
    def newScreen(self,screen:str) -> int:
        """Creates a new screen with some prompting

        Returns:
            0 Failed
            1 Success
        """
        #Check for valid filename  
        if not validName(screen):
            return 0
        
        with open(self.p_sinfo,"r") as f:
            info = json.load(f) #Load info

        name = self.title
        if info[name]["Screens"].get(screen) == None: #If Screen does not exist in VINFO
            while True: #ensures a valid name is used for script
                match input(f"Should python script use name {screen}.py? "):
                    case "Yes" | "yes" | "Y" | "y":
                        script = screen + ".py"
                        break
                    case _:
                        script = input("Enter the name for the script file: ").strip(".py")+".py"
                        if validName(script):
                            break

            match input("Should this screen have its own .exe?: "):
                case "Yes" | "yes" | "Y" | "y":
                    release = True
                case _:
                    release = False
            ictf =input("What is the icon for this screen (or none)?: ")
            icon = ictf.strip(".ico") if ".ICO" in ictf.upper() else None
            desc = input("Write a description for this screen: ")
            self.screenlist.append(Screen(screen,script,release,icon,False,desc))

            return 1
        else:
            print(f"Information for {screen} already in project.")
            return 1

    def hasScreen(self,screen:str) -> bool:
        """Checks if the project has the correct screen
        """
        for i in self.screenlist:
            if i.name == screen:
                return True
        return False
    
    def getScreen(self,screen:str) -> Screen:
        """Returns a screen object by its name
        """
        for i in self.screenlist:
            if i.name == screen:
                return i
        return None

    def verScreen(self,screen:str) -> Screen:
        """Verifies a screen exists and returns it

        Returns:
            screen (Screen): Verified screen
        """
        if not self.hasScreen(screen):
            self.newScreen(screen)
        scr = self.getScreen(screen)
        return scr

    def saveState(self)->None:
        """Saves the current project state to project.json | WILL FINISH THIS LATER"""
        with open(self.p_sinfo, "w") as f:
            info = {}
            info[self.name] = {}
            info[self.name]["Screens"] = {}