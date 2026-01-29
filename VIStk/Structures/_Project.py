import json
from VIStk.Structures._VINFO import *
from VIStk.Structures._Screen import *

class Project(VINFO):
    """VIS Project Object
    """
    def __init__(self):
        """Initializes or load a VIS project
        """
        super().__init__()
        self.screenlist:list[Screen]=[]
        """A List of `Screen` Objects in the Project"""
        with open(self.p_sinfo,"r") as f:
            info = json.load(f)

            for screen in list(info[self.title]["Screens"].keys()):
                scr = Screen(screen,
                             info[self.title]["Screens"][screen]["script"],
                             info[self.title]["Screens"][screen]["release"],
                             info[self.title]["Screens"][screen].get("icon"),
                             exists=True)
                self.screenlist.append(scr)
            self.d_icon = info[self.title]["defaults"]["icon"]

            self.dist_location:str = info[self.title]["release_info"]["location"]
            self.hidden_imports:list[str] = info[self.title]["release_info"]["hidden_imports"]
        self.Screen:Screen = None

    #Project Screen Methods
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
            if i.title == screen:
                return True
        return False
    
    def getScreen(self,screen:str) -> Screen:
        """Returns a screen object by its name
        """
        for i in self.screenlist:
            if i.title == screen:
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

    def setScreen(self,screen:str) -> None:
        """Sets the currently active screen"""
        self.Screen = self.getScreen(screen)

    def load(self, screen:str) -> None:
        """Loads a screen from screenlist
        
        Returns:
            (None): When load fails
        """
        try:
            self.getScreen(screen).load()
        except AttributeError:
            return None

    def reload(self) -> None:
        """Reloads the current screen
        
        Returns:
            (None): When load fails
        """
        try:
            self.Screen.load()
        except AttributeError:
            return None
