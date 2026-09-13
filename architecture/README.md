# Arch Linux on `aarch64`

Status: unofficial. Packages come from [Arch Linux Ports](https://ports.archlinux.page/aarch64/),
built outside Arch infrastructure and signed with the port's own key. Targets `ARMv8.2-A` and
later (no Raspberry Pi 4 or Cortex-A53 class CPUs).

## ISO

UEFI boards install with the regular `guided` script from the aarch64 archiso:

https://codeberg.org/ironrobin/archiso-aarch64/releases/latest

It boots through `EFI/BOOT/BOOTAA64.EFI`, ships `linux` as kernel, and its `pacman.conf`
already points at the port's repositories, so nothing has to be pointed anywhere.

## Repositories

| Repo | Content |
|------|---------|
| `core`, `extra` | analogues of the x86_64 repositories |
| `forge` | board kernels and firmware (`linux-rpi5`, `linux-mainline`, `linux-firmware-rpi5`), `archports-keyring`, Pi tooling |

All three live on `https://arch-linux-repo.drzee.net/arch/$repo/os/$arch`. The port's own
`pacman` package ships that conf, so the installed system resolves from it without a
mirrorlist. What differs from x86_64 inside archinstoo:

- Mirror regions are not offered (no mirror network). Custom servers and repos still are.
- `forge` is the optional repository, in place of `multilib` and the testing repos.
- `archports-keyring` joins the base packages: `pacman` does not depend on it there.
- The `microcode` initramfs hook is dropped, it only knows x86 vendors.
- Bootloaders: `systemd-boot`, `grub` (`arm64-efi`), `limine` (`BOOTAA64.EFI`).
- Serial console defaults to `ttyAMA0,115200`, the pl011 UART most boards expose.

Board kernels are plain package names: `"kernels": ["linux-rpi5"]` in a config reaches
`pacstrap` as is. The interactive kernel menu lists the stock kernels only.

## Running on an installed system

For non-UEFI systems where you went the hard-way with tarball modifications:

`./RUN --script live` opens a reduced menu for a system that already boots: no disk, no
bootloader, just users, packages, profiles and services.

## Dev VM from an x86_64 host

```shell
sudo pacman -S --needed qemu-system-aarch64 edk2-aarch64
A2_ARCH=aarch64 ./TVM              # window, ramfb
A2_ARCH=aarch64 A2_SERIAL=1 ./TVM  # headless, drive it with ./TSER
```

TCG emulation, expect minutes to a shell. The ISO is picked by the `aarch64` in its file
name under `isos/a/`. In the VM the console is a PCI 16550 (`ttyS0`), not the pl011, so a
config for it sets `"serial_console": "ttyS0,115200"`. See the header of `TVM` for the rest.
