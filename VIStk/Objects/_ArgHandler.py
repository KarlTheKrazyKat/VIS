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
        
    def handle(self, args):
        """Handles Arguments.

        Args:
            args (list | dict): A list of arguments (sys.argv) or a dict
                of {flag: value} pairs (Host navigation path).

        Returns:
            None if no registered flag matched any argument. Otherwise a
            list of the non-None values returned by the matched flag
            functions. A CLI command function returns a continuation
            ``(callable, args)``; a GUI flag function returns None (it just
            sets state), so the list can be empty even when a flag matched.
            The None-vs-list distinction lets a caller tell "unrecognized"
            (print a usage error) from "recognized" (act on it).
        """
        matched = False
        results = []

        if isinstance(args, dict):
            for key, value in args.items():
                for i, flag in enumerate(self.flags):
                    if key.lower() in [f.lower() for f in flag]:
                        matched = True
                        r = self.functions[i](
                            [value] if not isinstance(value, list) else value
                        )
                        if r is not None:
                            results.append(r)
            return results if matched else None

        if len(args) >= 1:
            if len(args) > 1 and args[0] == args[1]:
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
                        matched = True
                        r = self.functions[self.flags.index(_flag)](fargs)
                        if r is not None:
                            results.append(r)

        return results if matched else None
