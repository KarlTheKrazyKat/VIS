"""VIStk CLI message-passing helpers.

The Host runs a symmetric continuation-passing exchange between the
terminal-launched instance (``T``) and the running Host (``H``).  A
*continuation* is a ``(callable, args)`` pair: a function does its bit and
returns the next ``(callable, args)`` for the OTHER side to run.  Functions
cross the socket **by reference** (``module:qualname``) and are re-imported on
the far side -- both ends are the same binary, so any importable function
resolves.  Closures/lambdas cannot cross; args must be JSON-serializable.

Wire messages (length-prefixed JSON, 4-byte big-endian length):

    {"kind": "call", "fn": "module:qualname", "args": [...]}
    {"kind": "done"}

``H``-side functions run on the Tk main loop -- they must NOT block.
``T``-side functions run on T's own pump and may block (``input()`` etc.).
"""
from __future__ import annotations

import importlib
import json
from typing import Any, Callable

DONE: dict = {"kind": "done"}


# -- function-by-reference ----------------------------------------------------

def ref(fn: Callable) -> str:
    """Return an import reference ``module:qualname`` for *fn*."""
    return f"{fn.__module__}:{fn.__qualname__}"


def resolve(reference: str) -> Callable:
    """Import and return the callable named by ``module:qualname``."""
    mod_name, _, qual = reference.partition(":")
    obj: Any = importlib.import_module(mod_name)
    for part in qual.split("."):
        obj = getattr(obj, part)
    return obj


# -- continuation (de)serialization -------------------------------------------

def serialize_call(cont) -> dict:
    """Serialize a ``(callable_or_ref, args)`` continuation to a wire dict."""
    fn, args = cont
    fn_ref = fn if isinstance(fn, str) else ref(fn)
    return {"kind": "call", "fn": fn_ref, "args": list(args)}


def run_call(msg: dict):
    """Resolve and invoke the call in *msg*; return its continuation or None."""
    fn = resolve(msg["fn"])
    args = msg.get("args", [])
    return fn(*args)


# -- framing ------------------------------------------------------------------

def _recv_exact(conn, n: int) -> bytes | None:
    buf = b""
    while len(buf) < n:
        chunk = conn.recv(n - len(buf))
        if not chunk:
            return None
        buf += chunk
    return buf


def recv_msg(conn) -> dict | None:
    """Read one length-prefixed JSON message, or None if the peer closed or
    the socket errored."""
    try:
        raw_len = _recv_exact(conn, 4)
        if raw_len is None:
            return None
        length = int.from_bytes(raw_len, "big")
        if length <= 0 or length > 64 * 1024:
            return None
        data = _recv_exact(conn, length)
        if data is None:
            return None
        return json.loads(data.decode("utf-8"))
    except Exception:
        return None


def send_msg(conn, msg: dict) -> None:
    """Frame and send one JSON message."""
    data = json.dumps(msg).encode("utf-8")
    conn.sendall(len(data).to_bytes(4, "big") + data)


# -- native (VIStk-supplied) CLI commands -------------------------------------

def print_line(text: str):
    """T-side: print *text* to the terminal. Terminal of the chain (no
    continuation)."""
    print(text)


def host_ping(*_):
    """H-side: report from the running Host. Runs on the main thread, so it
    can read live Host state. Returns a T-side print continuation."""
    import os
    from VIStk.Objects._Host import _HOST_INSTANCE
    host = _HOST_INSTANCE
    nwin = len(host.detached_windows) if host is not None else 0
    return (print_line,
            (f"pong from Host pid={os.getpid()} open_windows={nwin}",))


def cmd_ping(fargs):
    """Producer for ``--ping``: returns the initial continuation, which runs
    on H."""
    return (host_ping, ())


def register_native(handler) -> None:
    """Register VIStk's built-in Host-level CLI commands on *handler* (an
    :class:`~VIStk.Objects._ArgHandler.ArgHandler`)."""
    handler.newFlag("ping", cmd_ping)
