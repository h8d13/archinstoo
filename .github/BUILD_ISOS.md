# Build your own ISOs

Scripts in `isos/` wrap `mkarchiso` to produce custom Arch ISOs. Run from the repo root.

| Script | Purpose |
|---|---|
| [`isos/ISOMOD`](../isos/ISOMOD) | Installer ISO with `archinstoo` baked in |
| [`isos/ISOMOD_LIVE`](../isos/ISOMOD_LIVE) | Live-mode KDE ISO |
| [`isos/ISOMOD_CACHE`](../isos/ISOMOD_CACHE) | Helper, pre-caches packages from `${iso_profile}.conf` |

Requires `archiso`. Add `pacman-contrib` if you enable caching. Don't run as root scripts elevate when needed.

Tweak behavior via env vars (or see the top of each script for the full list and defaults). Output goes to `isos/a/`.

> Do read through all of it (relatively short) to understand what is going on. Process takes about 5 minutes depending on packages selected.