# Alpha - Fedinstoo

## What is `fedinstoo`

A port of [`archinstoo`](https://github.com/h8d13/archinstoo) that installs [Fedora](https://fedoraproject.org)
instead of Arch Linux: same menus, same config files, same steps, with `dnf`, `dracut`
and `kernel-install` underneath.

The Python package is still named `archinstoo` while the port settles.

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

## How an install goes

1. Disk layout is partitioned, formatted and mounted under `/mnt`.
2. `dnf --installroot` straps `@core` (mandatory tier only), `dracut` and the picked firmware.
3. Locale (`glibc-langpack-*`), console, hostname, timezone, users, network, apps.
4. The bootloader goes in, then the kernel: its `kernel-install` run builds the initramfs and
   the boot entry (or UKI) from `/etc/kernel/cmdline`.
5. The tree is labeled for SELinux with the target's own `setfiles`, so it boots enforcing.

Bootloaders: GRUB (shim-signed, ESP at `/boot/efi`; BIOS too) and systemd-boot (BLS or UKI).

## Testing

Every change is tested the same way, from `BOOT` inside a VM ([`TVM`](TVM) + [`TSER`](TSER)):

```shell
A2_SERIAL=1 ./TVM                    # an Arch ISO from .dev-iso/ as the host
./TSER login && ./TSER push installer /root/fedinstoo/installer
./TSER push BOOT /root/fedinstoo/BOOT && ./TSER push RUN /root/fedinstoo/RUN
./TSER run 'cd /root/fedinstoo && ./BOOT --config <config> --silent'
./TSER quit && A2_SERIAL=1 ./TVM boot && ./TSER login -p test
```

Unit tests: `pytest -c installer/pyproject.toml installer/tests`

## Status

Ported and booted in QEMU (UEFI): minimal installs with GRUB and systemd-boot, ext4,
networkd/resolved, chrony, SELinux enforcing.

Not ported yet: desktop/server profile package names, graphics drivers (RPM Fusion),
disk encryption keyfiles, snapshots, packaging (the PKGBUILDs and release CI are still Arch's).

---

See [`archinstall`](https://github.com/archlinux/archinstall) and [`archinstoo`](https://github.com/h8d13/archinstoo),
which this builds on.
