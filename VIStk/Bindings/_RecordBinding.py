"""RecordBinding — links a dict record to a set of Tk widgets."""

import tkinter as tk
from tkinter import ttk


# --------------------------------------------------------------------- #
# Module-level widget value access registry                              #
# --------------------------------------------------------------------- #
# Maps widget class -> callable. Getters take ``(widget)`` and return
# the displayed value; setters take ``(widget, value)`` and write it.
# Resolution at bind/get/set time:
#   explicit override on bind()  ->  registered default for the widget's
#   class (MRO walk, so subclasses like AutocompleteEntry inherit the
#   Entry handler)  ->  ``getattr(widget, "get"/"set")`` if callable
#   ->  TypeError pointing at register_widget().

_DEFAULT_GETTERS: dict = {}
_DEFAULT_SETTERS: dict = {}

# Read-only state setters. Maps widget class -> ``fn(widget, locked: bool)``.
# Resolution mirrors value setters but with one important difference: the
# fallback for unknown widgets is a silent no-op, not an error. Read-only
# is advisory UI — the binding still enforces "can't enter modified" for
# any field whose policy says it's locked, regardless of whether the
# widget visually grays out.
_DEFAULT_READONLY_SETTERS: dict = {}


def _set_entry(widget, value):
    """Setter for Entry-shaped widgets, robust to readonly/disabled state.

    Note: ``widget.cget("state")`` returns a Tcl_Obj for ttk widgets and a
    plain string for tk widgets — coerce via ``str()`` before comparing.
    """
    state = str(widget.cget("state"))
    restore = state in ("readonly", "disabled")
    if restore:
        widget.config(state="normal")
    try:
        widget.delete(0, "end")
        widget.insert(0, "" if value is None else str(value))
    finally:
        if restore:
            widget.config(state=state)


def _set_text(widget, value):
    """Setter for tk.Text — full content replacement."""
    widget.delete("1.0", "end")
    widget.insert("1.0", "" if value is None else str(value))


# Stock tkinter widgets — register at import time. Most field-shaped
# widgets work out of the box; users only need register_widget() for
# custom widgets that don't expose .get()/.set().
_DEFAULT_GETTERS[tk.Entry] = lambda w: w.get()
_DEFAULT_SETTERS[tk.Entry] = _set_entry
_DEFAULT_GETTERS[ttk.Entry] = lambda w: w.get()
_DEFAULT_SETTERS[ttk.Entry] = _set_entry

_DEFAULT_GETTERS[tk.Label] = lambda w: w.cget("text")
_DEFAULT_SETTERS[tk.Label] = lambda w, v: w.config(text="" if v is None else v)
_DEFAULT_GETTERS[ttk.Label] = lambda w: w.cget("text")
_DEFAULT_SETTERS[ttk.Label] = lambda w, v: w.config(text="" if v is None else v)

_DEFAULT_GETTERS[tk.Text] = lambda w: w.get("1.0", "end-1c")
_DEFAULT_SETTERS[tk.Text] = _set_text

_DEFAULT_GETTERS[ttk.Combobox] = lambda w: w.get()
_DEFAULT_SETTERS[ttk.Combobox] = lambda w, v: w.set("" if v is None else v)

# tk.Spinbox is Entry-shaped (no native .set()); ttk.Spinbox does
# expose .set() but delete/insert works on both, so reuse _set_entry.
_DEFAULT_GETTERS[tk.Spinbox] = lambda w: w.get()
_DEFAULT_SETTERS[tk.Spinbox] = _set_entry
if hasattr(ttk, "Spinbox"):
    _DEFAULT_GETTERS[ttk.Spinbox] = lambda w: w.get()
    _DEFAULT_SETTERS[ttk.Spinbox] = _set_entry


def _readonly_via_state(widget, locked):
    """Toggle widgets that support state="readonly" / "normal"."""
    widget.config(state="readonly" if locked else "normal")


def _readonly_text(widget, locked):
    """tk.Text has no "readonly" state — use disabled / normal."""
    widget.config(state="disabled" if locked else "normal")


# Read-only handlers for the same widget classes that have value setters.
# Label is intentionally a no-op: it's already non-editable.
_DEFAULT_READONLY_SETTERS[tk.Entry]      = _readonly_via_state
_DEFAULT_READONLY_SETTERS[ttk.Entry]     = _readonly_via_state
_DEFAULT_READONLY_SETTERS[ttk.Combobox]  = _readonly_via_state
_DEFAULT_READONLY_SETTERS[tk.Spinbox]    = _readonly_via_state
if hasattr(ttk, "Spinbox"):
    _DEFAULT_READONLY_SETTERS[ttk.Spinbox] = _readonly_via_state
_DEFAULT_READONLY_SETTERS[tk.Text]       = _readonly_text
_DEFAULT_READONLY_SETTERS[tk.Label]      = lambda w, locked: None
_DEFAULT_READONLY_SETTERS[ttk.Label]     = lambda w, locked: None


def _resolve_getter(widget, override=None):
    if override is not None:
        return override
    for cls in type(widget).__mro__:
        if cls in _DEFAULT_GETTERS:
            return _DEFAULT_GETTERS[cls]
    fn = getattr(widget, "get", None)
    if callable(fn):
        return lambda w, _f=fn: _f()
    raise TypeError(
        f"no getter for widget of type {type(widget).__name__!r}: pass "
        f"getter= to bind() or register one via "
        f"RecordBinding.register_widget()"
    )


def _resolve_setter(widget, override=None):
    if override is not None:
        return override
    for cls in type(widget).__mro__:
        if cls in _DEFAULT_SETTERS:
            return _DEFAULT_SETTERS[cls]
    fn = getattr(widget, "set", None)
    if callable(fn):
        return lambda w, v, _f=fn: _f(v)
    raise TypeError(
        f"no setter for widget of type {type(widget).__name__!r}: pass "
        f"setter= to bind() or register one via "
        f"RecordBinding.register_widget()"
    )


def _resolve_readonly_setter(widget):
    """Resolve the read-only setter for *widget*.

    Walks ``type(widget).__mro__``; falls back to ``widget.set_readonly``
    if defined; otherwise returns a silent no-op. Unlike the value
    setter, missing read-only support is **not** an error — the binding
    still honors the policy in evaluate/refresh, the widget just doesn't
    visually gray out.
    """
    for cls in type(widget).__mro__:
        if cls in _DEFAULT_READONLY_SETTERS:
            return _DEFAULT_READONLY_SETTERS[cls]
    fn = getattr(widget, "set_readonly", None)
    if callable(fn):
        return lambda w, locked, _f=fn: _f(locked)
    return lambda w, locked: None


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

    Read-only semantics (#73):
      - The ``readonly`` argument to ``bind()`` is the *policy*, stored
        sparsely on the entry (``True`` or a callable; absent for False).
        Callables have signature ``(record_dict) -> bool`` and are
        re-evaluated against the current record on every ``refresh()``.
      - The widget's visual state is applied separately via the readonly
        setter registry (Entry/Combobox/Spinbox use ``state="readonly"``,
        Text uses ``state="disabled"``, Label is a no-op). Custom widgets
        with no registered handler silently no-op — read-only is advisory
        UI, not load-bearing; the binding still honors the policy below
        regardless of whether the widget grays out.
      - A field whose policy flips True->False between refreshes unlocks
        for editing on the next ``refresh()``; flipping False->True locks
        on the same boundary.
      - A read-only field cannot enter the modified state. ``evaluate()``
        skips read-only keys for edit detection (cheap per-frame); but
        ``refresh()`` still compares widget vs. record value for them, so
        external mutations to read-only fields are detected as divergence.

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
            ``True`` locks the field; a callable ``(record_dict) -> bool``
            is re-evaluated on every refresh. Falsy values are not
            stored. The widget's visual state is applied immediately via
            the readonly setter registry; the policy is also honored by
            ``evaluate()`` (skipped for edit detection) and ``refresh()``
            (still checked for divergence).
        getter, setter : callable, optional
            Override the default widget value access. Defaults are
            registered per widget class at module load (Entry, Label,
            Text, Combobox, Spinbox, ttk equivalents) and discovered via
            an MRO walk so subclasses inherit the parent class handler.
            For widgets without a registered handler, the binding falls
            back to ``widget.get`` / ``widget.set`` and finally raises a
            ``TypeError`` pointing at ``register_widget()``.
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

        # Populate the widget with the current record value (closes #71
        # acceptance item 2). Resolution failure surfaces here, on bind,
        # rather than later from evaluate() — which is when the caller
        # can still pass setter= or call register_widget().
        self._set(key, self._record[key])

        # Apply read-only state (#73). Done after the value write so the
        # final widget state matches the policy, regardless of whether
        # the widget started in normal/readonly/disabled.
        self._apply_readonly(key)

    def unbind(self, key):
        """Remove the registration for *key*.

        Idempotent — silent if *key* was not bound. The widget itself is
        left untouched (not destroyed, not cleared).
        """
        self._state.pop(key, None)

    def bound_keys(self):
        """Return the set of currently bound field keys."""
        return set(self._state)

    # ------------------------------------------------------------------ #
    # Widget value access (private)                                       #
    # ------------------------------------------------------------------ #

    def _get(self, key):
        """Read the current displayed value from the bound widget."""
        s = self._state[key]
        return _resolve_getter(s["widget"], s.get("getter"))(s["widget"])

    def _set(self, key, value):
        """Write *value* into the bound widget."""
        s = self._state[key]
        _resolve_setter(s["widget"], s.get("setter"))(s["widget"], value)

    # ------------------------------------------------------------------ #
    # Read-only handling (#73)                                            #
    # ------------------------------------------------------------------ #

    def _is_readonly(self, key):
        """Resolve the read-only policy for *key* against the current record.

        Returns ``True`` if the field is currently locked. Callable
        policies are invoked with the current ``self._record``.
        """
        policy = self._state[key].get("readonly")
        if policy is None:
            return False
        if callable(policy):
            return bool(policy(self._record))
        return bool(policy)

    def _apply_readonly(self, key):
        """Apply the resolved read-only state to the bound widget.

        Called from ``bind()`` and (per #75) from ``refresh()`` so a
        callable policy whose verdict has changed takes effect on the
        next refresh.
        """
        widget = self._state[key]["widget"]
        _resolve_readonly_setter(widget)(widget, self._is_readonly(key))

    # ------------------------------------------------------------------ #
    # Default registry (module-level, extensible)                         #
    # ------------------------------------------------------------------ #

    @classmethod
    def register_widget(cls, widget_class, getter=None, setter=None,
                        readonly_setter=None):
        """Register default handlers for *widget_class*.

        Pass any combination. The registry is module-level — registering
        once affects every ``RecordBinding`` instance, current and
        future. Resolution walks ``type(widget).__mro__``, so registering
        a base class is enough to cover its subclasses.

        Parameters
        ----------
        widget_class : type
            The widget class to register handlers for.
        getter : callable, optional
            Signature ``(widget) -> value``.
        setter : callable, optional
            Signature ``(widget, value) -> None``.
        readonly_setter : callable, optional
            Signature ``(widget, locked: bool) -> None``. Applies visual
            read-only state. If omitted for a widget class with no
            registered handler, read-only is silently a visual no-op
            (the binding still honors the policy in evaluate/refresh).
        """
        if getter is not None:
            _DEFAULT_GETTERS[widget_class] = getter
        if setter is not None:
            _DEFAULT_SETTERS[widget_class] = setter
        if readonly_setter is not None:
            _DEFAULT_READONLY_SETTERS[widget_class] = readonly_setter
