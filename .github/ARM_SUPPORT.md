# Arch Linux on `aarch64`

Status: unofficial. Packages come from [Arch Linux Ports](https://ports.archlinux.page/aarch64/),

## ISO

UEFI boards install with the regular `guided` script from the [aarch64 archiso](https://codeberg.org/ironrobin/archiso-aarch64/releases/latest)

## Repositories

| Repo | Content |
|------|---------|
| `core`, `extra` | analogues of the x86_64 repositories |
| `forge` | board kernels and firmware (`linux-rpi5`, `linux-mainline`, `linux-firmware-rpi5`), `archports-keyring`, Pi tooling |

What differs from x86_64 inside archinstoo:

- Mirror regions are not offered (no mirror network).
  Custom servers and repos still are.
- `forge` ships enabled in that conf, nothing to toggle. The optional repositories are
  `core-testing` and `extra-testing` only: no `multilib` on the port.
- `archports-keyring` joins the base packages: `pacman` does not depend on it there.
- The `microcode` initramfs hook is dropped, it only knows x86 vendors.
- Bootloaders: `systemd-boot`, `grub` (`arm64-efi`), `limine` (`BOOTAA64.EFI`).
- Serial console defaults to `ttyAMA0,115200`, the pl011 UART most boards expose.

Board kernels are plain package names:
`"kernels": ["linux-rpi5"]` in a config reaches `pacstrap` as is.
In the interactive kernel menu, `Custom (type a name)` takes the same names.

## Running on an already installed system

For non-UEFI systems where you went the hard-way with tarball modifications.

`./RUN --script packages` opens a reduced menu
for `Profile, Applications and Additional packages`
