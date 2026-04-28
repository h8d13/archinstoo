# Build your own ISOs

Scripts in `isos/` wrap `mkarchiso` to produce custom Arch ISOs. Run from the repo root.

| Script | Purpose |
|---|---|
| [`isos/ISOMOD`](../isos/ISOMOD) | Installer ISO with `archinstoo` baked in |
| [`isos/ISOMOD_CACHE`](../isos/ISOMOD_CACHE) | Helper, pre-caches packages from `${ISO_PROFILE}.conf` |

Flags (env vars, all optional):

| Var | Default | Effect |
|---|---|---|
| `LIVE` | `0` | `1` swaps the installer ISO for a Plasma live-session ISO (mutually exclusive with `MINIMAL`) |
| `MINIMAL` | `0` | `1` builds a small installer ISO from archiso `baseline` + network tools (`networkmanager`, `iwd`, `wpa_supplicant`, `dhcpcd`) + archinstoo runtime deps + all fs tools. Keeps archiso's stock 256M COW. Mutually exclusive with `LIVE` |
| `LIVE_USER` / `LIVE_PASS` | `live` / `live` | Credentials for the live user (LIVE=1 only) |
| `AUTOLOGIN` | `1` | SDDM autologin into Plasma (LIVE=1 only) |
| `CACHING` | `1` | Run `ISOMOD_CACHE` to bundle extra packages |
| `ISOMOD_BCACHEFS` | `0` | Add `bcachefs-dkms` and a oneshot module-build service |
| `COW_SIZE` | `1G` (LIVE=`2G`, MINIMAL=stock) | COW overlay size; MINIMAL inherits archiso default unless set |
| `THREADS` | `$(nproc)` | Build parallelism |
| `SILENT_MODE` | `0` | Swallow `mkarchiso` output |
| `PRECLEAN` | `0` | Wipe prior build artifacts before starting |
| `CLEANUP` | `1` | `0` keeps build dirs around |
| `LOG_FILE` | `1` | `0` skips the `z_isomod_*.log` |
| `ELEV` | `sudo` | Privilege escalation command (`doas`, etc.) |
| `ISO_PROFILE` | `ISOMOD_CACHE` | `ISOMOD_CACHE` reads `${ISO_PROFILE}.conf` for the package list |

Requires `archiso` and `pacman-contrib` if you enable caching. 

**Don't run as root**, scripts elevate when needed. Output goes to `isos/a/`.

> Do read through it (relatively short) to understand what is going on. Process takes 5 minutes depending on selections.

See [archiso-releng](https://gitlab.archlinux.org/archlinux/archiso/-/tree/master/configs/releng) and [archiso-baseline](https://gitlab.archlinux.org/archlinux/archiso/-/tree/master/configs/baseline) (used by `MINIMAL=1`).
