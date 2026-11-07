# Caeoma

[Caeoma](https://github.com/h8d13/caeoma) is an image-based Arch system
(submodule `caeoma/`). Its image carries archinstoo: boot it, then configure
it with the usual installer flow.

## 0. Get it

```console
git clone --recurse-submodules https://github.com/h8d13/archinstoo
```

In an existing checkout: `git submodule update --init`.

## 1. Build

Needs `mkosi`.

```console
isos/CAEOMA
```

The image lands in `caeoma/mkosi.output/caeoma_<version>.raw`.

## 2. Boot

Write it to a whole disk, it grows to fill it on first boot:

```console
sudo dd if=caeoma/mkosi.output/caeoma_<version>.raw of=/dev/sdX bs=4M conv=fsync status=progress
```

Log in as `root`, password `root`.

## 3. Configure

```console
pacman -Syu
cd /usr/share/archinstoo
python3 -m archinstoo --skip-base --skip-boot --skip-fstab
```

Base and kernel come from Caeoma's
[`mkosi.conf`](https://github.com/h8d13/caeoma/blob/master/mkosi.conf) (per
machine: [`mkosi.local.conf`](https://github.com/h8d13/caeoma/blob/master/mkosi.local.conf.example)),
its boot loader and mounts from its
[design](https://github.com/h8d13/caeoma/blob/master/docs/DESIGN.md): change
them there. In the menu:

- Disk configuration: **Pre-mounted configuration**, `/` (the box's own
  btrfs, as it is mounted; manual partitioning would have to unmount the disk
  the box runs from)
- Bootloader: none
- Swap: leave hibernation off, Caeoma brings its own swap file
- the rest as usual: root password, users, locale, timezone, profile,
  packages...

Then install. The changes are live right away.

## 4. Keep it

```console
caeoma commit
reboot
```

`commit` turns the new packages and their config into a new Caeoma version.
Users, passwords and hostname stay on the box either way.
`caeoma rollback` goes back to the version before.

