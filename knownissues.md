# Issues

## Unresolved

## Resolved

### Host / IPC — Resolved

#### Args passed to `Project.load()` are silently dropped over IPC

Found in 0.4.2
Fixed in 0.4.5

Resolved by removing the IPC layer entirely. `Project.open()` now routes through `_HOST_INSTANCE` in-process with `ArgHandler` dict support. Arguments are passed as a dict through `Project.open(name, args={...})`.

### HostMenu — Resolved

#### Menubar cascades permanently deleted when tab label matches project layer label

Found in 0.4.2
Fixed in 0.4.2

`clear_screen_items()` now deletes by index (reverse order) instead of label string.

### Form/Template

#### Relative path breaks after .exe is created

Found 0.3.3
Fixed 0.3.6

#### Form Extracts Wrong

Found 0.3.6
Fixed 0.3.7
