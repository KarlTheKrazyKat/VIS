class ArgHandler():
    def __init__(self):
        self.flags:list[list] = []
        """A List of Argument Flags"""
        self.functions:list[function]=[]
        """A List of Functions Corresponding to Flags"""

    def newFlag(self, keyword:str, method):
        """Creates a new flag linked to a method
        
        Args:
            keyword (str): The Keyword to Track
            method (function): The Function to Run
        """
        key1 = keyword.lower().capitalize()
        key2 = keyword.lower()
        key3 = key1[0]
        key4 = key2[0]
        for i in self.flags:
            if key4 in i:
                raise KeyError(f"Key {key1}[{key4}] Already Taken by {i[0]}[{i[3]}]")
            
        self.flags.append([key1,key2,key3,key4])
        self.functions.append(method)
        
    def handle(self, args:list):
        """Handles Arguments
        
        Args:
            args (list): A List of Arguments `sys.argv`
        """
        if len(args) > 1:
            if args[0] == args[1]:
                pargs = args[1:]
            else:
                pargs = args

            pargs = " ".join(pargs)
            pargs = pargs.split("--")

            for i in pargs:
                sargs = i.split(" ")
                flag = sargs[0]
                fargs = sargs[1:]

                for _flag in self.flags:
                    if flag in _flag:
                        self.functions[self.flags.index(_flag)](fargs)
