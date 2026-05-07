from VIStk.Structures._Screen import Screen


class Group:
    """A named collection of Screens within a Project.

    Groups are managed by their Project — typically obtained via
    ``project.groups[name]`` rather than constructed directly.

    A screen can belong to any number of named groups, and every screen
    in the project is also in the special ``"all"`` group.  ``"all"`` is
    auto-managed: it tracks the project's screens directly and cannot be
    mutated through ``add()`` / ``rem()``.
    """

    ALL = "all"

    def __init__(self, project, name: str, description: str = ""):
        self.project = project
        self.name = name
        self.description = description
        self.screenlist: list[Screen] = []

    # ── Inspection ────────────────────────────────────────────────────────

    def __contains__(self, item) -> bool:
        if isinstance(item, Screen):
            return item in self.screenlist
        return any(s.name == item for s in self.screenlist)

    def __iter__(self):
        return iter(self.screenlist)

    def __len__(self) -> int:
        return len(self.screenlist)

    def __bool__(self) -> bool:
        return bool(self.screenlist)

    def __repr__(self) -> str:
        return f"Group({self.name!r}, {len(self.screenlist)} screens)"

    def get(self, name: str) -> Screen | None:
        """Return the Screen with the given name, or None if not in this group."""
        for s in self.screenlist:
            if s.name == name:
                return s
        return None

    def names(self) -> list[str]:
        """Screen names in this group, in declared order."""
        return [s.name for s in self.screenlist]

    @property
    def is_all(self) -> bool:
        return self.name == self.ALL

    # ── Mutation ──────────────────────────────────────────────────────────

    def add(self, screen: Screen) -> None:
        """Add a screen to this group.  No-op if already a member."""
        if self.is_all:
            raise ValueError("'all' group is auto-managed; cannot add directly.")
        if screen in self.screenlist:
            return
        self.screenlist.append(screen)
        self.project._save_groups()

    def rem(self, screen: Screen) -> None:
        """Remove a screen from this group.  No-op if not a member."""
        if self.is_all:
            raise ValueError("'all' group is auto-managed; cannot remove directly.")
        if screen not in self.screenlist:
            return
        self.screenlist.remove(screen)
        self.project._save_groups()

    # ── Serialization ────────────────────────────────────────────────────

    def to_json(self) -> dict:
        """project.json form for this group (skip for 'all')."""
        return {
            "description": self.description,
            "screens": [s.name for s in self.screenlist],
        }
