# partstoob

Experimental ports `archinstoo` to run from **any Linux host** (not just Arch ISOs).


## Per distro host:

> Mostly tested from smallest **server type ISOs/cloud images**
> (see `./RUN --script dev.vm cloud fed|deb`).

Not fully cooked since it takes a lot of time, but at least all deps should be correct.

Can be found below:

| Logo | Host | `arch-install-scripts` | `pacman` | Script | Tested |
|------|------|------------------------|----------|--------|--------|
| <img src="https://github.com/h8d13/archinstoo/blob/master/distros/assets/deb_bw.svg?raw=1" width="32" alt="Debian"> | Debian | [V](https://packages.debian.org/sid/arch-install-scripts) | [V](https://packages.debian.org/sid/pacman-package-manager) | [DEB](https://github.com/h8d13/archinstoo/tree/master/distros/DEB) | V |
| <img src="https://github.com/h8d13/archinstoo/blob/master/distros/assets/nix_bw.svg?raw=1" width="32" alt="Nix"> | Nix | [V](https://github.com/NixOS/nixpkgs/blob/master/pkgs/by-name/ar/arch-install-scripts/package.nix) | [V](https://github.com/NixOS/nixpkgs/blob/master/pkgs/by-name/pa/pacman/package.nix) | [NIX](https://github.com/h8d13/archinstoo/blob/master/distros/flake.nix) | V |
| <img src="https://github.com/h8d13/archinstoo/blob/master/distros/assets/alp_bw.svg?raw=1" width="32" alt="Alpine"> | Alpine | [V](https://pkgs.alpinelinux.org/package/edge/community/x86_64/arch-install-scripts) | [V](https://pkgs.alpinelinux.org/package/edge/community/x86_64/pacman) | [ALP](https://github.com/h8d13/archinstoo/tree/master/distros/ALP) | V |
| <img src="https://github.com/h8d13/archinstoo/blob/master/distros/assets/fed_bw.svg?raw=1" width="32" alt="Fedora"> | Fedora | [V](https://packages.fedoraproject.org/pkgs/arch-install-scripts/arch-install-scripts/) | [V](https://packages.fedoraproject.org/pkgs/pacman/pacman/) | [FED](https://github.com/h8d13/archinstoo/tree/master/distros/FED) | V |

## Any host:

Instead of host packages, [`--script bootstrap`](https://github.com/h8d13/archinstoo/blob/master/installer/archinstoo/scripts/bootstrap.py)
runs archinstoo inside the [Arch bootstrap tarball](https://wiki.archlinux.org/title/Install_Arch_Linux_from_existing_Linux#Creating_a_chroot):
no pacman, keyring or `arch-install-scripts` on the host.

On aarch64 it takes the Arch Linux Ports tarball instead, see [`architecture/`](https://github.com/h8d13/archinstoo/blob/master/architecture).

A host _only_ needs:

```
python3 (>= 3.14) util-linux coreutils libarchive udev gnupg
```

`gnupg` is optional on x86_64 (checksum only without it, trusting TLS).

Package names might differ per distro.
`libarchive-tools` on Debian and Alpine, `bsdtar` on Fedora.

From Alpine (mdev by default):
`apk add python3 util-linux coreutils libarchive-tools gnupg eudev && setup-devd udev`

```shell
# what follows -- runs inside the root, as given (no args: guided)
./RUN --script bootstrap -- [archinstoo args...]
# the root is reused across runs, BOOT_DIR moves it (default /tmp/A2-boot)
# BOOT_MIRROR picks the x86_64 mirror for the tarball and packages
```

Everything runs inside the root: the tarball's own pacman, keyring and python,
with archinstoo's deps installed there on the first run.
Scripts that configure the running system (`packages`) are refused,
the root is thrown away after.
A layout mounted by hand on the host's `/mnt` is passed through for pre-mounted configs,
and the log path printed is the one the host sees.
