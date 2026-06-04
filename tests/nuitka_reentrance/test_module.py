"""Minimal probe module for the Nuitka re-entrance test.

We care about three things across multiple loads of this same file:

1. Identity: is module object the same or distinct across loads?
2. Module-level state: does setting ``counter`` on one load affect another?
3. Module-level mutable container: is ``items`` the same list object?

The two module-level globals start at known values. Each load assigns them
fresh, so if loads share state, the second load's view will not match a
mutation made through the first load's reference.
"""

counter = 0
items: list = []


def bump():
    """Mutate module-level state in two distinct ways.

    Reassignment of ``counter`` exercises STORE_GLOBAL (writes via
    PyDict_SetItem to module.__dict__).  Appending to ``items`` exercises
    in-place mutation of a shared object (which always crosses module
    boundaries because object identity is the same).
    """
    global counter
    counter += 1
    items.append(counter)
    return counter


def snapshot():
    """Return current values without mutating anything."""
    return {"counter": counter, "items": list(items), "items_id": id(items)}
