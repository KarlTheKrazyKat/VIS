"""Follow-up probe: characterize the PARTIAL result from Corner C.

Hypothesis: two .pyd loads create distinct module objects with distinct
__dict__s, but the function objects defined inside (bump, snapshot) are
shared and their __globals__ point to whichever module's PyInit ran most
recently.  If true, calling mod1.snapshot() after mod2 was loaded would
return mod2's state — silent non-determinism.
"""

import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PYD_PATH = os.path.join(HERE, "build", "test_module.cp313-win_amd64.pyd")


def fresh_load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


print(f"Python: {sys.version}")
print(f"PYD:    {PYD_PATH}\n")

mod1 = fresh_load("test_module", PYD_PATH)
print("--- After loading mod1 ---")
print(f"  mod1 id:                  {id(mod1)}")
print(f"  mod1.__dict__ id:         {id(mod1.__dict__)}")
print(f"  mod1.bump id:             {id(mod1.bump)}")
print(f"  mod1.snapshot id:         {id(mod1.snapshot)}")
print(f"  mod1.snapshot.__globals__ id: {id(mod1.snapshot.__globals__)}")
print(f"  mod1.snapshot.__globals__ is mod1.__dict__: {mod1.snapshot.__globals__ is mod1.__dict__}")

mod1.bump()
print(f"\n  After mod1.bump(): mod1.counter={mod1.counter}, mod1.items={mod1.items}")
print(f"  Direct read mod1.__dict__['counter']={mod1.__dict__['counter']}")
print(f"  Via mod1.snapshot(): {mod1.snapshot()}")

print("\n--- Loading mod2 (same name) ---")
mod2 = fresh_load("test_module", PYD_PATH)
print(f"  mod2 id:                  {id(mod2)}")
print(f"  mod2.__dict__ id:         {id(mod2.__dict__)}")
print(f"  mod2.bump id:             {id(mod2.bump)}")
print(f"  mod2.snapshot id:         {id(mod2.snapshot)}")
print(f"  mod2.snapshot.__globals__ id: {id(mod2.snapshot.__globals__)}")
print(f"  mod2.snapshot.__globals__ is mod2.__dict__: {mod2.snapshot.__globals__ is mod2.__dict__}")
print(f"  mod2.snapshot.__globals__ is mod1.__dict__: {mod2.snapshot.__globals__ is mod1.__dict__}")

print(f"\n  mod1 is mod2:                          {mod1 is mod2}")
print(f"  mod1.__dict__ is mod2.__dict__:        {mod1.__dict__ is mod2.__dict__}")
print(f"  mod1.bump is mod2.bump:                {mod1.bump is mod2.bump}")
print(f"  mod1.snapshot is mod2.snapshot:        {mod1.snapshot is mod2.snapshot}")
print(f"  mod1.snapshot.__globals__ is mod2.snapshot.__globals__: {mod1.snapshot.__globals__ is mod2.snapshot.__globals__}")

print("\n--- Now: read mod1's state AFTER mod2 was loaded ---")
print(f"  Direct read mod1.__dict__['counter']: {mod1.__dict__.get('counter')}")
print(f"  Direct read mod1.__dict__['items']:   {mod1.__dict__.get('items')}")
print(f"  Direct read mod2.__dict__['counter']: {mod2.__dict__.get('counter')}")
print(f"  Direct read mod2.__dict__['items']:   {mod2.__dict__.get('items')}")
print(f"  mod1.snapshot() returns:              {mod1.snapshot()}")
print(f"  mod2.snapshot() returns:              {mod2.snapshot()}")

print("\n--- Bump mod2, then check both module dicts directly ---")
mod2.bump()
print(f"  Direct mod1.__dict__['counter']:      {mod1.__dict__.get('counter')}")
print(f"  Direct mod1.__dict__['items']:        {mod1.__dict__.get('items')}")
print(f"  Direct mod2.__dict__['counter']:      {mod2.__dict__.get('counter')}")
print(f"  Direct mod2.__dict__['items']:        {mod2.__dict__.get('items')}")
print(f"  mod1.snapshot() returns:              {mod1.snapshot()}")
print(f"  mod2.snapshot() returns:              {mod2.snapshot()}")
