# Logs and config

For bug reports, share `install.log`. `Logger path:` at startup prints its
exact location.

| Where | Path |
| --- | --- |
| During the run | `~/.local/state/archinstoo/install.log` (`$XDG_STATE_HOME` if set) |
| Installed system | `/etc/archinstoo.d/<timestamp>_install.log` |

On the ISO the state directory is tmpfs, so after reboot only the copy in
`/etc/archinstoo.d/` remains.

`user_configuration.json` sits next to the log and can be resumed on a later
run. Disk and user/root passwords are never saved. `--clean` wipes the
directory.
