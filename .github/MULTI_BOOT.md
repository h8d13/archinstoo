# Multi Operating Systems

> Easiest way is to use **seperate disks** (this limits cases of overwriting important data)

Second is to check that your hardware supports `Other OS` secure boot options if planning to use with Windows 11.

Then simply: follow this section of the [wiki](https://wiki.archlinux.org/title/GRUB#Detecting_other_operating_systems)

Make sure you have `os-prober` package installed

1. Uncomment `GRUB_DISABLE_OS_PROBER=false` in `/etc/default/grub`

2. Regen `grub-mkconfig -o /boot/grub/grub.cfg`

This can also be achieved through custom entries using `blkid` in `/etc/grub.d/40_custom`

*Other bootloaders* have their own ways of doing this.