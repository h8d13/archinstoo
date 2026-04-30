# Dependency hell and minimalism

Basically to figure out why some things turn out the way they do:

Using `pacman-contrib` we can explore full dep trees. This simulates the install flow and counts/parses recursive deps.

```shell
./RUN --script count examples/config-sample-full.json --why polkit

{'bluez', 'intel-media-driver', 'libpulse', 'inotify-tools', 'mesa', 'cups', 'pipewire-pulse', 'micro', 'opendoas', 'base', 'vulkan-intel', 'timeshift', 'pipewire-alsa', 'pacman-contrib', 'gst-plugin-pipewire', 'wireplumber', 'pipewire', 'grub', 'system-config-printer', 'iwd', 'fail2ban', 'zram-generator', 'linux-zen', 'bottom', 'btrfs-progs', 'gdm', 'libva-intel-driver', 'pipewire-jack', 'networkmanager', 'ufw', 'git', 'linux-firmware', 'man-db', 'efibootmgr', 'syncthing', 'chromium', 'grub-btrfs', 'cups-pk-helper', 'bluez-utils'}

Explicit packages: 39
Resolving dependencies...
  39/39 | resolved: 574

Total packages (with deps): 574

'polkit' is pulled in by 3 explicit package(s):
  cups-pk-helper
  gdm
  networkmanager
```

This is useful before commiting to an install and understanding why certain things always do end up on your system (regardless of choices).
For a `seatd` only setup we'll have to jump a few hoops: Network option `Copy from ISO` or `iwd standalone` other NM options pull in `polkit`.
