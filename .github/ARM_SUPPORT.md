# Arch Alarm

This method is more advanced and assumes you've **built a stage 1 correctly.**

This usually involves the following:

- Extracted tarball onto a storage device. 
- Format/mount
- Replaced kernel with appropriate for hardware
- Hw specifics in `config.txt` or `boot.txt`
- Setup `/etc/fstab` and `cmdline.txt`

At this stage you should have a minimal install with only kernel/and bootloader.

This usually involves using `qemu-user-static qemu-user-static-binfmt` from an Arch host.

---


