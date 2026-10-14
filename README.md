# Alpha - Fedinstoo

## What is `fedinstoo`

A port of [`archinstoo`](https://github.com/h8d13/archinstoo) that installs [Fedora](https://fedoraproject.org)
instead of Arch Linux: same menus, same config files, same steps, with `dnf`, `dracut`
and `kernel-install` underneath.


## Setup / Usage

The installer runs from a Fedora root. [`BOOT`](BOOT) provides one on any Linux host
(an Arch ISO, Debian, Alpine, ...): it fetches the Fedora Container Base image, checks
it against Fedora's signed `CHECKSUM`, unpacks it and runs the installer inside.

A host only needs `python3 util-linux coreutils udev`, plus `gnupg` for the signature check.

```shell
git clone https://github.com/h8d13/fedinstoo
cd fedinstoo
sudo ./BOOT [args]   # try --help; some options are behind --advanced
```

| Env | Default | |
|-----|---------|-|
| `BOOT_DIR` | `/tmp/F2-boot` | where the root lives, reused across runs |
| `BOOT_RELEASE` | newest under `releases/` | Fedora release to install |
| `BOOT_MIRROR` | `download.fedoraproject.org` | mirror the image comes from |

From an installed Fedora, `./RUN` works directly (host-to-target): its own `dnf` provides the deps.

---

See [`archinstall`](https://github.com/archlinux/archinstall) and [`anaconda`](https://github.com/rhinstaller/anaconda),
which this project builds upon.

> It aims to fix two of my problems at once. One, arch linux as a whole lacks enough trusted maintainers/reporters.
> Which mostly impacts packaging efforts. But their installer is one of my favorite projects...
> and two, `anaconda` forcing too many defaults on official install mediums, instead of handing back to the user.


