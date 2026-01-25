# BAMBY to Arch

## Flashing the USB

You can use [rufus](https://rufus.ie/) for Winslows or [KDEImageWriter](https://apps.kde.org/isoimagewriter/) from Linux (or dd)
> Select mbr/gpt according to your hardware (usually gpt for newer hardware) 

Then when pressing "start" **use dd mode** for full copy.

After install, do not forget to **remove or change boot orders** in motherboard settings.
This is usually f2, f10, f12 or DEL or other combinations depending on manufacturers.

## More tips in the menu 

`/` allows you to search

`CTRL + C` allows you to clear the current menu

`hjkl` also allow you to move around (just like arrow keys)

`CTRL + H` shows the full help

When setting up a user you can also clone dotfiles directly and will be in `/home/user/.stash`

## Languages Compat 🌐

Before running the post install script you can uncomment any of these lines for extended support:
```shell
noto-fonts-cjk         # Chinese, Japanese, Korean
noto-fonts-extra       # Full extended symbols
```
In additional packages section. 


## Maintaining your system

I am stuck:
```shell
CTRL + ALT + Fx
# x being an F key nbr
```
This should let you access a tty

I dont know what I'm looking for:
```shell
pacman -Qi pkg
# pacman -Ql pkg
pacman -Q | grep <pkg>
```

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
sudo pacman -Sy
```

