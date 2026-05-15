from VIStk.Widgets._VISMenu import *
from VIStk.Widgets._ScrollableFrame import *

class ScrollMenu(ScrollableFrame):
    """A Scrollable Menu"""
    def __init__(self, root:Widget, data:dict, *args, **kwargs):
        super().__init__(root, *args, **kwargs)
        self.VISMenu = VISMenu(self.scrollable_frame, data)
        """The `VISMenu` Object"""