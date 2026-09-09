# BAMBY to Arch

## Flashing the USB

You can use [rufus](https://rufus.ie/) for Winslows or [KDEImageWriter](https://apps.kde.org/isoimagewriter/) from Linux (or dd)
> Select mbr/gpt according to your hardware (usually gpt for newer hardware)

Then when pressing "start" **use dd mode** for full copy.

After install, do not forget to **remove or change boot orders** in motherboard settings.
This is usually f2, f10, f12 or DEL or other combinations depending on manufacturers.

Do check that you are using your best hub/USB keys (usually blue USBs are for 3.x+ or even better in USB-C)
If install speed matters to you.

## More tips in the menu

Take your time, **installing is fast**, make sure you went through everything you might need.

> [!TIP]
> Looking up your motherboard model, CPU/GPU, memory, disks, etc... Can often save you lots of headaches.
> You can use `lspci` and `lsusb`. `Firmware` > `full` detects the optional vendor packages your hardware needs (Marvell, Mellanox, QLogic and friends), which the base `linux-firmware` does not carry. `vendor` is for trimming that down by hand.

You may view main schema here: [Menu-Preview](./SCHEMA.md)

Typing lets you search in multi-select menus.

ARROW keys lets you move around.

`CTRL + C` allows you to clear the current menu

`CTRL + H` shows the full help

When setting up a user you can also clone dotfiles directly and will be in `/home/user/.stash`

## Desktop vs Window Manager

If you are brand new to archlinux full desktops are simpler to handle (`KDE Plasma`, `GNOME`, `Cinnamon`, `Cosmic` and the likes)
Since a lot can be handled through GUI and not config files.

> [!NOTE]
> You may want to install one of these first instead of a WindowManager where more **manual work** is expected.
> If you do want a WM, we recommend using your **own config files** instead of the "dotfile" culture, you'll learn more and have a system tailored to you.

## Languages compat

You can add Google fonts for extended language support and setup multiple keyboards once you have a basic system working.
```shell
noto-fonts-cjk         # Chinese, Japanese, Korean
noto-fonts-extra       # Full extended symbols
```
In `Additional packages` section.

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
Do not chain `-Syu && -S <pkg>` either: declining the upgrade prompt leaves the db synced,
so the second command becomes the partial upgrade.

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
