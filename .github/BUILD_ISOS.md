# Build your own ISOs

## Intro

Scripts in `isos/` wrap `mkarchiso` to produce custom Arch ISOs. Run from the repo root.

| Script | Purpose |
|---|---|
| [`isos/ISOMOD`](https://github.com/h8d13/archinstoo/blob/master/isos/ISOMOD) | Installer ISO with `archinstoo` baked in |
| [`isos/ISOMOD_CACHE`](https://github.com/h8d13/archinstoo/blob/master/isos/ISOMOD_CACHE) | Helper, pre-caches packages from `${A2_ISO_PROFILE}.conf` |

## Configure

Flags (env vars, all optional):

| Var | Default | Effect |
|---|---|---|
| `A2_LIVE` | `0` | `1` swaps the installer ISO for a Plasma live-session ISO (mutually exclusive with `A2_MINIMAL`) |
| `A2_MINIMAL` | `0` | `1` builds a small installer ISO from archiso `baseline` + network tools (`networkmanager`, `iwd`, `wpa_supplicant`, `dhcpcd`) + archinstoo runtime deps + all fs tools. Keeps archiso's stock 256M COW. Mutually exclusive with `A2_LIVE` |
| `A2_LIVE_USER` / `A2_LIVE_PASS` | `live` / `live` | Credentials for the live user (A2_LIVE=1 only) |
| `A2_AUTOLOGIN` | `1` | SDDM autologin into Plasma (A2_LIVE=1 only) |
| `A2_CACHING` | `0` | `1` runs `ISOMOD_CACHE` to bundle extra packages |
| `A2_BCACHEFS` | `0` | Add `bcachefs-dkms` and a oneshot module-build service |
| `A2_COW_SIZE` | `1G` (A2_LIVE=`2G`, A2_MINIMAL=stock) | COW overlay size; A2_MINIMAL inherits archiso default unless set |
| `A2_THREADS` | `$(nproc)` | Build parallelism |
| `A2_SILENT_MODE` | `0` | Swallow `mkarchiso` output |
| `A2_PRECLEAN` | `0` | Wipe prior build artifacts before starting |
| `A2_CLEANUP` | `1` | `0` keeps build dirs around |
| `A2_LOG_FILE` | `1` | `0` skips the `z_isomod_*.log` |
| `A2_ELEV` | `sudo` | Privilege escalation command (`doas`, etc.) |
| `A2_ISO_PROFILE` | `ISOMOD_CACHE` | `ISOMOD_CACHE` reads `${A2_ISO_PROFILE}.conf` for the package list |

Requires `archiso` and `pacman-contrib` if you enable caching. This is a flagship feature that allows for read-only installs (no network).

**Don't run as root**, scripts elevate when needed. Output goes to `isos/a/`.

> Do read through it (relatively short) to understand what is going on. Process takes 5 minutes depending on selections.

See [archiso-releng](https://gitlab.archlinux.org/archlinux/archiso/-/tree/master/configs/releng) and [archiso-baseline](https://gitlab.archlinux.org/archlinux/archiso/-/tree/master/configs/baseline) (used by `A2_MINIMAL=1`).

Size references: Minimal ~550M - Regular ~1.4G - Live ~2G
