# CachyOS kernels

## Switching

Install normally, then swap kernels after first boot. Keeps stock kernel as fallback.

1. Boot the installed system
2. Add [`Cachyos-repos`](https://github.com/h8d13/cachyos-repos) then run `sudo ./cachyos-repo --install`
3. `pacman -Syy linux-cachyos` (and any additional drivers you might need from their repos)
4. Regen bootloader: `grub-mkconfig -o /boot/grub/grub.cfg` (or equivalent depending on bootloader and paths)
5. Reboot, pick the new kernel entry in the menu.

Optionally after checking all works fine, remove the repos (`--remove`).

## Details

Simply because we want an arch base:
Details are available in the [repo](https://github.com/h8d13/cachyos-repos) itself.

- Do not replace pacman
- Do not insert cachyos repos before regular ones

Can specify as `pacman -S cachyos/appname` or `cachyos-vX/linux-variant`

That's it.
