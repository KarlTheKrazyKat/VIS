"""Monotonic in-process ID allocator.

VIStk 0.4.7 replaces display-name-based lookups for tabs, panes, and
windows with stable integer IDs. All IDs come from a single
module-level counter so they are globally unique for the lifetime of
the Python process; this makes them safe to move across panes or
windows without renumbering and easy to grep for in debug logs.

The counter is **not** persistent — IDs reset on process restart.
Persistent identity for features like "remember open tabs across
restart" would need UUIDs or a saved highwater mark; that is out of
scope for 0.4.7.
"""

from __future__ import annotations

import itertools
import threading

_counter = itertools.count(1)
_lock = threading.Lock()


def new_id() -> int:
    """Return a fresh, strictly increasing integer ID.

    Thread-safe; may be called from any thread (tab drag handlers run on
    the Tk main thread today but future IPC / async work may not).
    """
    with _lock:
        return next(_counter)
