# Documentation

## Commands

### Project Creation

Initialize new project in current folder

```cmd
VIS new
```

Will provide a series of prompts in order to setup a blank project

Accepted as:

- `New`
- `new`
- `N`
- `n`

### Screen Creation

Initialize a new screen in the project

```cmd
VIS add screen <screen_name>
```

Will setup a new blank screen ready for compiling to .exe if assigned. A series of prompts will aid creation.

Accepted as:

- `Add`
- `add`
- `A`
- `a`

and

- `Screen`
- `screen`
- `S`
- `s`

### Element Creation

Initialize a new element (frame) on a screen

```cmd
VIS add screen <screen_name> elements <element_name>
```

Will create new frames and bind them to the screen based on the default templates. Additionally this command can be used to create a new screen and populate it with elements in one line.

To add multiple elements in one call the element names should be seperated by "-" and contain no spaces.

```cmd
VIS add screen <screen_name> elements <element_1>-<element_2>-<element_3>
```

Accepted as:

- `Elements`
- `elements`
- `E`
- `e`

## Building Screens and Modules

### Warnings

#### Handling tkinter root

One of the most important things to have screen switching properly function is to not destroy root. If root gets destroyed by a subprocess the program may not longer function correctly since VIStk will not be able to reuse the root to switch screens. Instead of calling root.destroy() you should set root.Active = False. The default template will break the while True loop when root.Active == False and python will stop the window by default since the script will reach its end.

Therefore, equally as important is that root.mainloop() is not started. This will bypass the default screen behavior and can only be escaped on root.destroy(); Hence initiating the aforementioned error.

#### Using VIS templates

It is very import not to delete or modify in any way the lines that are commented with `#%` as these lines denote VIS searchable sections. This means that VIStk will attempt to search for this header and its following header to define a block of code. VIStk does this to automatically connect modules and screens to their parent script.

If the VIS extension is installed it will automatically recolor these comments differently than normal comments.
