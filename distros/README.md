# partstoob

Experimental ports `archinstoo` to run from **any Linux host** (not just Arch ISOs).


## Per distro host:

> Mostly tested from smallest **server type ISOs/cloud images** (see `./distros/CLOUD fed|deb`).

Not fully cooked since it takes a lot of time, but at least all deps should be correct.

Can be found below:

| Logo | Host | `arch-install-scripts` | `pacman` | Script | Tested |
|------|------|------------------------|----------|--------|--------|
| <img src="https://github.com/h8d13/archinstoo/blob/master/distros/assets/deb_bw.svg?raw=1" width="32" alt="Debian"> | Debian | [V](https://packages.debian.org/sid/arch-install-scripts) | [V](https://packages.debian.org/sid/pacman-package-manager) | [DEB](https://github.com/h8d13/archinstoo/tree/master/distros/DEB) | V |
| <img src="https://github.com/h8d13/archinstoo/blob/master/distros/assets/nix_bw.svg?raw=1" width="32" alt="Nix"> | Nix | [V](https://github.com/NixOS/nixpkgs/blob/master/pkgs/by-name/ar/arch-install-scripts/package.nix) | [V](https://github.com/NixOS/nixpkgs/blob/master/pkgs/by-name/pa/pacman/package.nix) | [NIX](https://github.com/h8d13/archinstoo/blob/master/distros/flake.nix) | V |
| <img src="https://github.com/h8d13/archinstoo/blob/master/distros/assets/alp_bw.svg?raw=1" width="32" alt="Alpine"> | Alpine | [V](https://pkgs.alpinelinux.org/package/edge/community/x86_64/arch-install-scripts) | [V](https://pkgs.alpinelinux.org/package/edge/community/x86_64/pacman) | [ALP](https://github.com/h8d13/archinstoo/tree/master/distros/ALP) | V |
| <img src="https://github.com/h8d13/archinstoo/blob/master/distros/assets/fed_bw.svg?raw=1" width="32" alt="Fedora"> | Fedora | [V](https://packages.fedoraproject.org/pkgs/arch-install-scripts/arch-install-scripts/) | [V](https://packages.fedoraproject.org/pkgs/pacman/pacman/) | [FED](https://github.com/h8d13/archinstoo/tree/master/distros/FED) | V |

## Any host:

Instead of host packages, [`BOOT`](https://github.com/h8d13/archinstoo/blob/master/distros/BOOT) runs archinstoo inside a
[Arch bootstrap tarball](https://wiki.archlinux.org/title/Install_Arch_Linux_from_existing_Linux#Creating_a_chroot).

On aarch64 it takes the Arch Linux Ports tarball instead, see [`architecture/`](https://github.com/h8d13/archinstoo/blob/master/architecture):

A host _only_ needs:

```
bash util-linux curl zstd tar coreutils gnupg
```

`gnupg` is optional on x86_64 (checksum only without it).

From Alpine (mdev by default): `apk add bash curl zstd tar coreutils util-linux gnupg eudev && setup-devd udev`

```shell
# point to ram
# export BOOT_DIR=/tmp/a2-boot
./distros/BOOT [archinstoo args...]
```
