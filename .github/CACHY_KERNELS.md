# CachyOS kernels

## Switching

Install normally, then swap kernels after first boot. Keeps stock kernel as fallback.

1. Boot the installed system
2. Add [`Cachyos-repos`](https://github.com/h8d13/cachyos-repos) then run `sudo ./cachyos-repo --install`
3. `pacman -Syy linux-cachyos` (and any additional drivers you might need from their repos)
4. Regen bootloader: `grub-mkconfig -o /boot/grub/grub.cfg` (or equivalent depending on bootloader and paths)
5. Reboot, pick the new kernel entry in the menu.

Optionally after checking all works fine, remove the repos (`--remove`).

## Their userspace packages, at install time

"Additional packages" lists every repo section in the live `/etc/pacman.conf`, nothing
hardcoded. So cachyos packages are selectable during the install, two ways in:

- Run archinstoo from a host that already has the repos (`./cachyos-repo --install`
  beforehand). They show up with no extra step.
- Or add them in the installer under Pacman config, custom repositories.

Either way `pacstrap -C /etc/pacman.conf` straps from that same file, so what you
select installs into the target. The conf is then copied to the installed system,
so the repos are still there after first boot (`file://` entries get stripped).

Custom repos are appended after the stock ones, so conf order keeps core and extra
winning any name clash. Same rule as below, enforced by where they land.

## Details

Simply because we want an arch base:
Details are available in the [repo](https://github.com/h8d13/cachyos-repos) itself.

- Do not replace pacman
- Do not insert cachyos repos before regular ones

Can specify as `pacman -S cachyos/appname` or `cachyos-vX/linux-variant`

That's it.
