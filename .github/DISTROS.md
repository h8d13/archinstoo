# Other Linux

From any Linux host, [`--script bootstrap`](https://github.com/h8d13/archinstoo/blob/master/installer/archinstoo/scripts/bootstrap.py)
runs archinstoo inside the [Arch bootstrap tarball](https://wiki.archlinux.org/title/Install_Arch_Linux_from_existing_Linux#Creating_a_chroot):
no pacman, keyring or `arch-install-scripts` on the host. On aarch64 it takes the Arch Linux Ports tarball instead,
see [ARM / aarch64 ports](ARM_SUPPORT.md).

> Mostly tested from the smallest **server type ISOs/cloud images** (see `./CLOUD fed|deb`).

The host _only_ needs:

```
python3 (>= 3.14) util-linux coreutils libarchive udev gnupg
```

`gnupg` is optional on x86_64 (checksum only without it, trusting TLS). libarchive's `bsdtar` is
`libarchive-tools` on Debian and Alpine, `bsdtar` on Fedora.

From Alpine (mdev by default): `apk add python3 util-linux coreutils libarchive-tools gnupg eudev && setup-devd udev`

```shell
# what follows -- runs inside the root, as given (no args: guided)
./RUN --script bootstrap -- [archinstoo args...]
# the root is reused across runs, BOOT_DIR moves it (default /tmp/A2-boot)
# BOOT_MIRROR picks the x86_64 mirror for the tarball and packages
```

Everything runs inside the root: the tarball's own pacman, keyring and python, with archinstoo's deps
installed there on the first run. Scripts that configure the running system (`packages`) are refused, the
root is thrown away after. A layout mounted by hand on the host's `/mnt` is passed through for pre-mounted
configs, and the log path printed is the one the host sees.

## Per distro host packages

These distros package `pacman` and `arch-install-scripts` themselves. Before `--script bootstrap`, archinstoo
ran straight on them from those packages, with a setup script each. That route is retired: the installer
now refuses a non-Arch host and points it at the bootstrap. The scripts stay in history, linked below.

| Logo | Host | `arch-install-scripts` | `pacman` | Script (last version) | Tested |
|------|------|------------------------|----------|-----------------------|--------|
| <img src="assets/deb_bw.svg" width="32" alt="Debian"> | Debian | [V](https://packages.debian.org/sid/arch-install-scripts) | [V](https://packages.debian.org/sid/pacman-package-manager) | [DEB](https://github.com/h8d13/archinstoo/blob/0811515edaa60b1053d10c408c4354f6fc4624df/distros/DEB) | V |
| <img src="assets/nix_bw.svg" width="32" alt="Nix"> | Nix | [V](https://github.com/NixOS/nixpkgs/blob/master/pkgs/by-name/ar/arch-install-scripts/package.nix) | [V](https://github.com/NixOS/nixpkgs/blob/master/pkgs/by-name/pa/pacman/package.nix) | [NIX](https://github.com/h8d13/archinstoo/blob/0811515edaa60b1053d10c408c4354f6fc4624df/distros/flake.nix) | V |
| <img src="assets/alp_bw.svg" width="32" alt="Alpine"> | Alpine | [V](https://pkgs.alpinelinux.org/package/edge/community/x86_64/arch-install-scripts) | [V](https://pkgs.alpinelinux.org/package/edge/community/x86_64/pacman) | [ALP](https://github.com/h8d13/archinstoo/blob/0811515edaa60b1053d10c408c4354f6fc4624df/distros/ALP) | V |
| <img src="assets/fed_bw.svg" width="32" alt="Fedora"> | Fedora | [V](https://packages.fedoraproject.org/pkgs/arch-install-scripts/arch-install-scripts/) | [V](https://packages.fedoraproject.org/pkgs/pacman/pacman/) | [FED](https://github.com/h8d13/archinstoo/blob/0811515edaa60b1053d10c408c4354f6fc4624df/distros/FED) | V |
