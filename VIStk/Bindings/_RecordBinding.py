"""RecordBinding — links a dict record to a set of Tk widgets."""


class RecordBinding:
    """Links a dict-shaped record to a set of bound widgets.

    Tracks per-field state (equal, modified, diverged, read-only), fires
    callbacks on transitions, and exposes a commit path back to the source.
    Layout is unconstrained — widgets stay where the screen put them, and
    the binding manages the dict-widget relationship in parallel.

    Storage shape (private — never accessed directly by users; all reads
    and writes go through binding methods):

        self._record               # the source dict, supplied by the caller
        self._state = {
            field_key: {
                "widget":   <Tk widget>,        # always present
                "edited":   True,               # absent unless user has edited
                "readonly": True | callable,    # absent unless field is read-only
                "getter":   fn(widget) -> value,    # absent unless caller overrode
                "setter":   fn(widget, value),  # absent unless caller overrode
            },
            ...
        }

    Conventions:
      - Default entry is one key (`widget`); optional flags are added only
        when set, so `state.get("edited")` / `state.get("readonly")` are
        the correct truthiness checks.
      - Widgets are stored by reference. Callers must `unbind()` before
        destroying a widget; stale references will raise `TclError` on
        access.
      - Fresh widget values are read on demand via the resolved getter —
        the binding does not cache the widget value.

    Record vs. state coverage:
      - A record key with no bound widget is carried as-is on the record
        and ignored by state evaluation.
      - Binding a key that is not present in the record raises ``KeyError``
        (decided in #70 to keep `bind()` strict; see #71 acceptance).

    This class is being built incrementally — storage shape lands in #70;
    bind/unbind/bound_keys in #71; getter/setter dispatch in #72;
    read-only handling in #73; evaluate/refresh in #74/#75; callbacks
    in #76; commit in #77.
    """

    def __init__(self, record):
        self._record = record
        self._state = {}
