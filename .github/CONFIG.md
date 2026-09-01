# Configuration

## Intro

When using `archinstoo` a config file is saved in the logger directory,
alongside `install.log`. The file is named: `user_configuration.json`

This file can be saved and resumed to be used another time.
This is handy if you want to go back to the terminal quickly before installling.

**DISK AND USER/ROOT PASSWORDS** are never resumed.

---

## Where it lands

The directory belongs to the user who ran the command, not to the source
checkout, the install layout, or the directory you launched it in. Source and
installed, `sudo` and not, all land in the same place for a given user:

| Running | Directory |
| --- | --- |
| Anything, as a user (`./RUN`, `sudo ./RUN`, `archinstoo`, `--script list`) | `$XDG_STATE_HOME/archinstoo/`, default `~/.local/state/archinstoo/` |
| Real root, no invoking user (ISO, autologin, `su -`) | `/root/.local/state/archinstoo/` |

Under `sudo` the path comes from the invoking user's passwd entry, so root's
`HOME` and `XDG_STATE_HOME` do not pull the logs into `/root`.

`Logger path:` is printed at startup with the exact file.

On the ISO the state directory is tmpfs and dies with the live session. The
copy that survives is written into the installed system, at
`/etc/archinstoo.d/<timestamp>_install.log` and `_config.json`.

`--clean` wipes that directory, saved configuration included.

---

## Backwards-compat

Your configuration might need editing if you use the program again later.
But perhaps a lot of it will work exactly the same.

Examples configurations can be found in the repo ranging from very simple to complex.
But the best is to create your own through the menu.
