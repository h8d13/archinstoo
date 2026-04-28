# CachyOS kernel

Install Arch normally with `linux`, then swap kernels after first boot. Keeps stock kernel as fallback.

1. Boot the installed system
2. Add CachyOS repos: [`COSAI`](https://github.com/h8d13/COSAI)
3. `pacman -Sy linux-cachyos` (and any additional drivers you might need from their repos)
4. Regen bootloader: `grub-mkconfig -o /boot/grub/grub.cfg` (or equivalent)
5. Reboot, pick the CachyOS kernel.

Optionally after checking all works fine, remove the original kernel/headers.