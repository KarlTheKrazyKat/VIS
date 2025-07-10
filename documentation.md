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
