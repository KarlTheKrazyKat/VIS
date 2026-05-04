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

    # ------------------------------------------------------------------ #
    # Registration                                                        #
    # ------------------------------------------------------------------ #

    def bind(self, key, widget, readonly=False, getter=None, setter=None,
             replace=False):
        """Register *widget* against record *key*.

        Parameters
        ----------
        key : hashable
            Field name in the bound record.
        widget : Tk widget
            Stored by reference; the caller must ``unbind()`` before
            destroying the widget.
        readonly : bool or callable, optional
            ``True`` locks the field; a callable ``(record) -> bool`` is
            re-evaluated on every refresh. Falsy values are not stored.
            (Behavioural application of read-only state lands in #73.)
        getter, setter : callable, optional
            Override the default widget value access. Defaults are
            registered per widget class in #72; until that lands the
            initial widget population (#71 acceptance item 2) is
            deferred — callers that need it immediately should pass an
            explicit ``setter`` and call it themselves.
        replace : bool, optional
            If a widget is already bound to *key*, ``replace=True`` swaps
            it in; otherwise ``ValueError`` is raised.

        Raises
        ------
        KeyError
            If *key* is not present in the bound record.
        ValueError
            If *key* is already bound and *replace* is False.
        """
        if key not in self._record:
            raise KeyError(
                f"cannot bind {key!r}: key not in record "
                f"(call bind() only for fields the record actually carries)"
            )
        if key in self._state and not replace:
            raise ValueError(
                f"key {key!r} is already bound; pass replace=True to override"
            )

        entry = {"widget": widget}
        if readonly:
            entry["readonly"] = readonly
        if getter is not None:
            entry["getter"] = getter
        if setter is not None:
            entry["setter"] = setter
        self._state[key] = entry

    def unbind(self, key):
        """Remove the registration for *key*.

        Idempotent — silent if *key* was not bound. The widget itself is
        left untouched (not destroyed, not cleared).
        """
        self._state.pop(key, None)

    def bound_keys(self):
        """Return the set of currently bound field keys."""
        return set(self._state)
