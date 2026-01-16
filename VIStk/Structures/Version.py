class Version():
    """A Version number"""
    def __init__(self, version:str):
        """Creates a Version Number Object from a string"""
        nums = version.split(".")
        self._major=int(nums[0])
        self._minor=int(nums[1])
        self._patch=int(nums[2])

    def __str__(self) -> str:
        return f"{self._major}.{self._minor}.{self._patch}"
    
    def major(self):
        """Increases the major release number"""
        self._major += 1
        self._minor = 0
        self._patch = 0

    def minor(self):
        """Increases the minor release number"""
        self._minor += 1
        self._patch = 0

    def patch(self):
        """Inscreases the patch release number"""
        self._patch += 1