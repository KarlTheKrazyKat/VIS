# VIStk Host CLI Mode — Design Handoff

**Date:** 2026-05-20
**Status:** Design converged. No code written. Builds on PR #143 (`host-single-instance`), which is open and NOT compile-tested.
**Tracking issue:** https://github.com/KarlTheKrazyKat/VIS/issues/144 (rewritten to match this doc)
**Repo:** KarlTheKrazyKat/VIS — branch to build on: `host-single-instance`

> Carry-forward note: line numbers below are on the `host-single-instance` branch.
> The whole point of this feature is a non-GUI run-and-exit path for the
> always-Host `<project>.exe`, with **no mode flag** — what the args resolve to
> decides GUI vs CLI, not a switch the user types.

---

## The principle

There is **no `--command` / `--cli` switch**. Args route to wherever the user
points them (a screen, or the Host). The *function* the args resolve to decides
what happens: open a window, or produce terminal output. Unrecognized args →
a CLI error printed locally. Nobody should have to type a mode flag.

---

## Architecture: symmetric two-pump message passing

Two roles, **same shape**:

- **H** — the running, persistent Host (Tk mainloop).
- **T** — the instance the terminal just launched.

Each has three parts:
1. a **queue**,
2. a **loop** that pumps the queue,
3. a **bridge thread** that moves messages between the socket and the queue
   (`V` on the Host, `TV` on the terminal instance).

`V` and `TV` can be the **same class**; H's pump and T's pump can share a base.
The symmetry is the payoff — one mechanism, used twice.

### H's pump already exists (on the branch)
- **V (listener thread):** `_ipc_accept_loop` — daemon thread, accepts a
  connection, parses JSON, `self._ipc_queue.put(...)` (`_Host.py:214`, put at `:238`).
- **The pump:** `_drain_ipc_queue` — drains `_ipc_queue` on the Tk main thread,
  called every frame from `update()` (`_Host.py:251`, called at `:534`).
- Today the item is hard-coded `(screen, args)` and the drain only opens windows.

### T's pump is new
A plain blocking loop, **no Tk** — `while not done: item = queue.get(); run it`.
Plus `TV`, the mirror of `V`.

---

## Message model

- A message is **`(function-by-reference, args, reply_to)`**.
- **Functions cross by reference**, e.g. `("modules.lrfEditor.cli", "show_record", (path,))`,
  resolved by import on the far side. Works because both ends are the same binary.
  Closures/lambdas can't cross; args must be picklable.
- **Continuation-passing.** A function does its bit and **returns the next
  `(fn, args)`** for the other side to run. Nobody blocks on a cross-process
  reply. The only blocking call in the system is `input()`, local to T.
  - Trade-off: continuation-passing is deadlock-proof, but a command author
    writes a *chain* of small functions instead of linear code. A synchronous
    `host_call()` that blocks T's pump is also safe (T has nothing else to do
    while it waits); the two can coexist. **Default to continuation-passing.**

---

## reply_to and termination

- **Invariant:** every received message produces **exactly one** response over
  its `reply_to` — either a continuation `(fn, args)` or a terminal marker.
  H always replies; no `reply_to` dangles.
- **T's exit condition:** queue empty **AND** outstanding-count == 0
  (increment on send, decrement on response). Because H always replies,
  termination is provable — T can always reach exit.
- **Concrete change required:** the listener currently does `with conn:` and
  closes the socket after one request (`_Host.py:222`). `reply_to` needs the
  connection kept open as the reply channel. Two options:
  - **Most symmetric:** each side binds a listener; a message carries the
    sender's reply address; the far side connects back to reply.
  - **Simplest:** one persistent duplex socket held open for the whole exchange.

---

## ArgHandler stays dumb

- It remains a **pure router**: argv → registered function. The *registered
  functions* are authored to produce the initial `(fn, args)`. ArgHandler
  itself produces nothing and classifies nothing.
- **Only change:** `handle()` returns **`None`** when nothing matches, so T
  prints a usage error locally and never bothers H. (Today it silently no-ops
  on unknown flags.)

---

## H-side vs T-side function rules

- **H-side functions must NOT block** — they run on the Tk mainloop; `input()`
  or a long sync wait there freezes the GUI.
- **T-side functions may block freely** — no GUI to freeze. Interactive/blocking
  work lives in T; GUI/state work lives in H. The *same* function isn't runnable
  on both sides.
- Free property: H's queue serializes everything onto the main thread, so
  concurrent terminals need **no locking** on H state.

---

## No running Host

- With no instance running, **T runs both sides on its own pump, in-process**
  (loopback — no second process, no socket).
- Then the launch rule:
  - **VIStk-native command** (`screenname *args`, or no args) → T spins up the
    real GUI Host and stays.
  - **Anything else** → T runs the chain headless and **exits**.
- Native commands are VIStk-supplied; that is what keeps GUI-launch from being
  per-flag classification — only the built-in screen-launcher shows a window.

---

## Console / packaging

Interactive CLI requires the invoked binary to be **console-subsystem** (so the
shell waits and `input()` works). That's a PE header bit, read *before* the
process runs — **not** changeable at runtime. Runtime tricks (`AttachConsole`,
Nuitka `attach`/`hide` console modes) give no-flash output but lose wait+input,
so they don't satisfy interactive CLI.

**No console flash is a hard requirement.** Resolution differs by OS:

### Windows — two binaries
- `WOM.exe` — **GUI subsystem**. Shortcuts / double-click → no console, no flash.
- `WOM.com` — **console subsystem**. Typed `wom` resolves to `.com` first
  (default PATHEXT is `.COM;.EXE;…`), so it waits and `input()` works, with no
  flash because it is already inside the shell's console.
- When the console binary hits *no-H + native*, it **spawns `WOM.exe`** as the
  Host rather than hosting the GUI itself (a console-subsystem process should
  not own the long-lived GUI).
- Caveat to verify in practice: a PE renamed `.com` is a known-good trick but
  can occasionally trip AV/SmartScreen heuristics.

### Linux — one binary, no flash exists
- No subsystem concept, so no flash, ever.
- From a terminal: inherits stdin/stdout, shell waits (normal foreground).
  From a `.desktop` entry: no terminal, GUI only.
- Same architecture: T prints and exits fast; the persistent H is
  `setsid`/daemonized so the terminal isn't held for the GUI session.

So only `_Release.py`'s **Windows** path builds the second binary; Linux stays
single-binary.

---

## Files in play (NOT yet edited — design only)

| File | Change |
|---|---|
| `VIStk/Objects/_Host.py` | Generalize queue item to `(fn, args, reply_to)`; drain runs `fn` and sends the reply; keep `conn` open as the reply channel; factor `V`/pump for reuse; no-H path runs both sides in-process (native→GUI Host, else headless) |
| `VIStk/Objects/_ArgHandler.py` | `handle()` returns `None` on no-match; router otherwise unchanged |
| *(new)* T-side pump + `TV` bridge | Plain non-Tk loop + mirror of `V`; ideally shares a base/class with the Host side |
| `VIStk/Structures/_Release.py` | Windows: also build a console-subsystem `WOM.com`; Linux: unchanged single binary + daemonize H on first launch |

---

## Dependencies & gotchas

- Stacks on **PR #143** (`host-single-instance`) — single-instance socket mutex,
  forward-to-primary, and the IPC queue this design generalizes. #143 is open and
  **not compile-tested**.
- Today T forwards then goes inert (`Active=False`, `_Host.py:64`) and exits.
  This design needs T to forward, then **stay alive** running its own pump until
  its exit condition is met. `_forward_to_primary` (`_Host.py:183`) becomes the
  send side of a request/response exchange.
- **`gh pr edit` is broken in this repo** (deprecated project-cards GraphQL,
  exit 1). Use the REST API for edits:
  `gh api -X PATCH repos/KarlTheKrazyKat/VIS/issues/<n> -f body=...`

---

## Open items (decide during implementation — not blockers)

1. Continuation-passing as the default vs an optional synchronous `host_call()`.
2. Reply channel: per-side listeners (most symmetric) vs one persistent duplex
   socket (simplest).
3. Verify `.com` behavior against AV/SmartScreen on a real install.

---

## Where to pick up

1. Confirm PR #143 is the base; check it out (`host-single-instance`).
2. Generalize the Host queue item + drain (`_Host.py`), keeping `conn` open.
3. Build the T-side pump + `TV` as a shared class with `V`.
4. Make `ArgHandler.handle()` return `None` on no-match.
5. Wire the no-H in-process path + the native-vs-headless rule.
6. `_Release.py`: second console binary on Windows; daemonize H; Linux single.
7. Only then test — full release required (Host exe + installer change).
