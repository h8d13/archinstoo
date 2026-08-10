# Configuration

## Intro

When using `archinstoo` a config file is saved in the logger directory,
alongside `install.log`. The file is named: `user_configuration.json`

This file can be saved and resumed to be used another time.
This is handy if you want to go back to the terminal quickly before installling.

**DISK AND USER/ROOT PASSWORDS** are never resumed.

---

## Where it lands

The directory comes from where `archinstoo` is installed, not from the
directory you launched it in:

| Running | Directory |
| --- | --- |
| From source (`./RUN`, `./DEV`) | `installer/logs/` |
| Installed, as root | `/var/log/archinstoo/` |
| Installed, rootless scripts (`list`, `size`, `mirror`, `count`) | `$XDG_STATE_HOME/archinstoo/`, default `~/.local/state/archinstoo/` |

`Logger path:` is printed at startup with the exact file.

`--clean` wipes that directory, saved configuration included.

---

## Backwards-compat

Your configuration might need editing if you use the program again later.
But perhaps a lot of it will work exactly the same.

Examples configurations can be found in the repo ranging from very simple to complex.
But the best is to create your own through the menu.
