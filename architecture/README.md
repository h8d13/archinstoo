# Arch Alarm

Stage 1 builders for non-x86 targets. Currently ARM (Arch Linux ARM).

```
architecture/
  ARM         entry script: generic stage 1 (partition, extract, base setup)
  boards/     one profile per device, sourced by ARM
```

## Intro

This method is more advanced. A **stage 1** usually involves:

- Extracted tarball onto a storage device. [Tarballs](https://archlinuxarm.org/about/downloads)
- Format/mount
- Replaced kernel with appropriate for hardware
- (Hw specifics in `config.txt` or `boot.txt`)
- (Setup `/etc/fstab` and `cmdline.txt`)

At this stage you should have a minimal install with only kernel/and bootloader/FS.

This involves using `qemu-user-static qemu-user-static-binfmt` from an x86 Arch host
(runs the ARM chroot emulated; not needed from an ARM host).

## Usage

List available boards, then build onto a target device:

```shell
./architecture/ARM list
sudo ./architecture/ARM rpi5 /dev/sdX
```

The script needs the board's tarball and finds it one of three ways:

1. Already downloaded, sitting next to the script or in cwd:
   ```shell
   curl -LO http://os.archlinuxarm.org/os/ArchLinuxARM-rpi-aarch64-latest.tar.gz
   ```
2. Anywhere else, passed as explicit path:
   ```shell
   sudo ./architecture/ARM rpi5 /dev/sdX ~/Downloads/ArchLinuxARM-rpi-aarch64-latest.tar.gz
   ```
3. Not downloaded at all, let the script fetch it:
   ```shell
   sudo FETCH=1 ./architecture/ARM rpi5 /dev/sdX
   ```

The core does everything generic: msdos label, fat32 boot + ext4 root,
tarball extract with dirty-page progress, keyring init, locale, fstab
by PARTUUID, wired DHCP, getty/sshd/networkd/resolved enabled.
The board profile handles what differs per device: kernel/bootloader
swap, `cmdline.txt`, firmware config. `rpi5` (Pi 5 Model B) swaps the
generic `linux-aarch64` kernel for `linux-rpi` + foundation firmware.

**Default credentials after boot:**
- `root:root`
- `alarm:alarm`

Once in, `passwd && passwd alarm`, or better yet create a new user.

## Adding a board

Copy `boards/rpi5`, adjust. A board file is sourced by `ARM` and can set:

| What | Required | Purpose |
|------|----------|---------|
| `ARCHIVE` | yes | tarball filename |
| `TARBALL_URL` | no | enables `FETCH=1` and the download hint |
| `BOARD_CHROOT` | no | shell run inside the chroot (kernel/bootloader swap) |
| `board_finish()` | no | after chroot: cmdline, firmware config, boot cleanup. `$MNT`, `$BOOT_PARTUUID`, `$ROOT_PARTUUID`, `$DEVICE` in scope |
| `board_partition()` | no | replaces default partitioning entirely (exotic layouts, U-Boot at raw offsets) |

Boards whose tarball boots as shipped (generic `linux-aarch64` +
working U-Boot) need only `ARCHIVE` and `TARBALL_URL`.

---

## Using the `live` script

At this point we assume you have a working boot setup and a tty or access to terminal.

This is a reduced version of `guided` that only aims to setup certain stuff.

> Removes bootloaders and more things that are not needed for a running system.

Then `./RUN --script live` will bring you to a minimal menu that is aimed to run on a live system.

Through this you can set-up server usecases or desktops and more utilities you might need.

<img width="1920" height="1080" alt="Screenshot 2026-02-05 15-32-36" src="https://github.com/user-attachments/assets/a0bdf9cd-a472-48f8-a5fc-7d5467381a30" />
