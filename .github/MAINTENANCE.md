## Maintaining your system

I am stuck stepbro:
```shell
CTRL + ALT + Fx
# x being an F key nbr
```
This should let you access a tty, from there you can try to kill the problematic process or fix the issue.

I dont know what I'm looking for:
```shell
pacman -Qi pkg
# pacman -Ql pkg
pacman -Q | grep <pkg>
```

You can also `|` (pipe) to other useful stuff like `less`, `head`, `tail`, etc...

I want to learn about something:
```shell
pacman -S man-db
man <pkg>
```

I want to have a clean system:
```shell
pacman -S pacman-contrib
# tools for pacman
paccache -r
# cleans cache
checkupdates
bash-completion 2.17.0-1 -> 2.17.0-2
mkinitcpio 40-3 -> 40-4
# visit archlinux.org/news ideally before updating
# limit AUR usage to strictly necessary
```

I have slow mirrors:
```shell
sudo reflector --protocol https --latest 20 --sort rate --save /etc/pacman.d/mirrorlist
sudo pacman -Syyu
# -yy forces db re-download (new mirror may differ), -u keeps it a full upgrade
# -Sy / -Syy alone are the partial upgrade trap, see below
```

### Partial upgrades

Arch is rolling: every package is built against the current libs.
Syncing the db (`-Sy`) then installing anything without also upgrading (`-u`)
pulls in a package linked against sonames the rest of your system does not have yet.
Result: random binaries fail with `error while loading shared libraries`.
[Partial upgrades are unsupported](https://wiki.archlinux.org/title/System_maintenance#Partial_upgrades_are_unsupported).

```shell
# avoid
sudo pacman -Sy <pkg>       # sync + install, no upgrade
sudo pacman -Sy             # sync now...
sudo pacman -S <pkg>        # ...install later, same problem
# instead, one command
sudo pacman -Syu <pkg>
```

Same applies to `-Syy` (only forces the db re-download), `-Syuw` and `IgnorePkg`.

> [!TIP]
> To peek at pending updates without touching the db, use `checkupdates` (`pacman-contrib`): it syncs into a temp copy.

### Kernel upgrades

The kernel package owns `/usr/lib/modules/<version>/`. Upgrading swaps that dir for the new version,
so modules for the **running** kernel are gone. Anything not already loaded fails until reboot:
new USB devices, fs types, `tun`/`wireguard`, bridges (docker), etc...
Check `checkupdates` for `linux*` and [reboot after upgrading](https://wiki.archlinux.org/title/System_maintenance#Restart_or_reboot_after_upgrades).

> [!TIP]
> [`kernel-modules-hook`](https://archlinux.org/packages/extra/any/kernel-modules-hook/) (`extra`)
> keeps the old dir around until reboot. Install, then `systemctl enable linux-modules-cleanup`.
