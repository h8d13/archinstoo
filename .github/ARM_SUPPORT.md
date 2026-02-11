# Arch Alarm

This method is more advanced and assumes you've **built a stage 1 correctly.**

This usually involves the following:

- Extracted tarball onto a storage device. [Tarballs](https://archlinuxarm.org/about/downloads)
- Format/mount
- Replaced kernel with appropriate for hardware
- (Hw specifics in `config.txt` or `boot.txt`)
- (Setup `/etc/fstab` and `cmdline.txt`)

At this stage you should have a minimal install with only kernel/and bootloader/FS.

This usually involves using `qemu-user-static qemu-user-static-binfmt` from an x86 Arch host.

---

## Example Stage 1 for Rasp Pi 5 Model B Rev 1.0

This script is specifically for the Pi 5 Model B. Other Pi models may need different kernels and boot configurations.

Stole a lot of parts of code from what I found online and slapped it all together.
Sorry if credits got lost...

**Default credentials after boot:**
- `root:root`
- `alarm:alarm`

**Download the tarball first:**
```shell
curl -LO http://os.archlinuxarm.org/os/ArchLinuxARM-rpi-aarch64-latest.tar.gz
```

Placed in the same location as the following:

```shell
#!/bin/bash

# this example is built to support rasp pi 5 model B

# sudo pacman -S qemu-user-static qemu-user-static-binfmt
# this enables to run ARM arch-chroot emulated from your x86 host
# so not needed if doing this from ARM host

# this script will setup a stage 1 for ARM
# fomratting/mounting
# replacing the kernel and firmware
# do some very basic set-up (ssh/locale/tty/fstab/cmdline/bootparams)

# once in, passwd && passwd alarm
# or better yet create a new user

[[ $EUID -ne 0 ]] && { echo "Run as root"; exit 1; }

# IMPORTANT: Verify your target device with lsblk before running.
# Wrong device = wiped drive.
DEVICE="/dev/sdb"
ARCHIVE="ArchLinuxARM-rpi-aarch64-latest.tar.gz"

# Boot partition needs room for kernel, initramfs, and firmware.
# 512MiB is generally enough but can bump to 1GiB if space allows.
END_S="513MiB"

############ MAGIC RESET
#wipefs -a "$DEVICE"
#sudo umount -l /mnt/boot 2>/dev/null; sudo umount -l /mnt 2>/dev/null; sudo umount -l /dev/sdc1 2>/dev/null; sudo umount -l /dev/sdc2 2>/dev/null

parted -s -a optimal "$DEVICE" mklabel msdos
parted -s -a optimal "$DEVICE" mkpart primary fat32 1MiB $END_S
parted -s -a optimal "$DEVICE" mkpart primary ext4 $END_S 100%
parted -s "$DEVICE" set 1 boot on

mkfs.vfat -F 32 "${DEVICE}1" 
mkfs.ext4 -F "${DEVICE}2" 

mount "${DEVICE}2" /mnt
mkdir /mnt/boot
mount "${DEVICE}1" /mnt/boot

bsdtar -xpf "$ARCHIVE" -C /mnt &
BSDTAR_PID=$!
while kill -0 $BSDTAR_PID 2>/dev/null; do
    dirty=$(awk '/Dirty:/{print $2}' /proc/meminfo)
    printf "\rExtracting... Dirty: %'d kB  " "$dirty"
    sync &
    sleep 1
done
wait $BSDTAR_PID
echo ""

# vconsole.conf — must exist before linux-rpi installs (mkinitcpio needs it)
cat > /mnt/etc/vconsole.conf << 'EOF'
KEYMAP=us
EOF

# Locale setup
echo "en_US.UTF-8 UTF-8" > /mnt/etc/locale.gen
echo "LANG=en_US.UTF-8" > /mnt/etc/locale.conf

# Initialize pacman keyring and swap to Pi 5-compatible kernel
echo "Setting up chroot and installing linux-rpi kernel..."
arch-chroot /mnt /bin/bash -c '
    sed -i "/^\[options\]/a DisableSandbox" /etc/pacman.conf
    pacman-key --init
    pacman-key --populate archlinuxarm
    pacman -Rns --noconfirm linux-aarch64 uboot-raspberrypi
    pacman -Sy --noconfirm linux-rpi raspberrypi-bootloader firmware-raspberrypi openssh
    locale-gen
'

# Remove leftover U-Boot script files (but NOT kernel files — linux-rpi manages those)
rm -f /mnt/boot/boot.scr /mnt/boot/boot.txt /mnt/boot/mkscr

# Add os_check=0 to whatever config.txt the packages set up (don't overwrite)
grep -q "os_check" /mnt/boot/config.txt || sed -i '1i os_check=0' /mnt/boot/config.txt

# Fix fstab — default references mmcblk0p1 which doesn't exist on USB boot
BOOT_PARTUUID=$(blkid -s PARTUUID -o value "${DEVICE}1")
ROOT_PARTUUID=$(blkid -s PARTUUID -o value "${DEVICE}2")
cat > /mnt/etc/fstab << EOF
# <file system>             <dir>   <type>  <options>       <dump>  <pass>
PARTUUID=${ROOT_PARTUUID}   /       ext4    defaults        0       1
PARTUUID=${BOOT_PARTUUID}   /boot   vfat    defaults        0       2
EOF
echo "root=PARTUUID=${ROOT_PARTUUID} rw rootwait console=tty1 console=ttyAMA10,115200 quiet loglevel=0 audit=0" > /mnt/boot/cmdline.txt

# Verify kernel is on boot partition
echo "Boot partition kernel files:"
find /mnt/boot -maxdepth 1 \( -name "Image*" -o -name "kernel*" -o -name "initramfs*" \) -exec ls -lh {} + 2>/dev/null || echo "WARNING: No kernel found on boot partition!"

# Enable DHCP on all ethernet interfaces.
# This only covers wired. For Wi-Fi I set it up through archinstoo menu network section
mkdir -p /mnt/etc/systemd/network
cat > /mnt/etc/systemd/network/20-wired.network << 'EOF'
[Match]
Name=en*

[Network]
DHCP=yes
EOF

############ Enable some basic services manually (initial access)
# Default target
ln -sf /usr/lib/systemd/system/multi-user.target /mnt/etc/systemd/system/default.target

# getty on tty1
mkdir -p /mnt/etc/systemd/system/getty.target.wants
ln -sf /usr/lib/systemd/system/getty@.service /mnt/etc/systemd/system/getty.target.wants/getty@tty1.service

# sshd — also generate host keys since sshd won't start without them
ssh-keygen -A -f /mnt
mkdir -p /mnt/etc/systemd/system/multi-user.target.wants
ln -sf /usr/lib/systemd/system/sshd.service /mnt/etc/systemd/system/multi-user.target.wants/sshd.service

# networkd + resolved
ln -sf /usr/lib/systemd/system/systemd-networkd.service /mnt/etc/systemd/system/multi-user.target.wants/systemd-networkd.service
ln -sf /usr/lib/systemd/system/systemd-resolved.service /mnt/etc/systemd/system/multi-user.target.wants/systemd-resolved.service

echo ""
echo "Final sync... (This can take a while if you have a slow USB)"
sync &
SYNC_PID=$!
while kill -0 $SYNC_PID 2>/dev/null; do
    dirty=$(awk '/Dirty:/{print $2}' /proc/meminfo)
    printf "\rFlushing... Dirty: %'d kB remaining  " "$dirty"
    sleep 1
done
wait $SYNC_PID
printf "\rFlushing... Done!                        \n"
echo "Unmounting..."
umount /mnt/boot /mnt
############
```

---

## Using the `live` script

At this point we assume you have a working boot setup and a tty or access to terminal.

This is a reduced version of `guided` that only aims to setup certain stuff. 

> Removes bootloaders and more things that are not needed for a running system.

First `./DEV -h2t` downloads dependencies you may need (from the PKGBUILD). 

Then `./RUN --script live` will bring you to a minimal menu that is aimed to run on a live system. 

Through this you can set-up server usecases or desktops and more utilities you might need.


<img width="1920" height="1080" alt="Screenshot 2026-02-05 15-32-36" src="https://github.com/user-attachments/assets/a0bdf9cd-a472-48f8-a5fc-7d5467381a30" />

