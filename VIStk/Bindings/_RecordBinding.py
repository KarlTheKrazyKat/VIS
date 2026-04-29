"""Stub for RecordBinding. Full implementation lands in subsequent issues."""


class RecordBinding:
    """Links a dict-shaped record to a set of bound widgets.

    Tracks per-field state (equal, modified, diverged, read-only), fires
    callbacks on transitions, and exposes a clean commit path back to the
    source. Layout is unconstrained — widgets stay where the screen put
    them, and the binding manages the dict-widget relationship in parallel.

    This is a stub. Storage shape, bind/unbind, evaluate/refresh, callbacks,
    and commit are added by later issues in the RecordBinding v1 tracker.
    """

    def __init__(self, record):
        self._record = record
