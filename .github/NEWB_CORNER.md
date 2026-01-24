# BAMBY to Arch

## Flashing the USB

You can use [rufus](https://rufus.ie/) for Winslows or [KDEImageWriter](https://apps.kde.org/isoimagewriter/) from Linux (or dd)
> Select mbr/gpt according to your hardware (usually gpt for newer hardware) 

Then when pressing "start" **use dd mode** for full copy.

## More tips in the menu 

`/` allows you to search

`CTRL + C` allows you to clear the current menu

`hjkl` also allow you to move around (just like arrow keys)

`CTRL + H` shows the full help

## Languages Compat 🌐

Before running the post install script you can uncomment any of these lines for extended support:
```
noto-fonts-cjk"         # Chinese, Japanese, Korean
noto-fonts-extra"       # Full extended symbols
```
In additional packages section. 


## Maintaining your system

I dont know what I'm looking for:
```
pacman -Qi pkg
# pacman -Ql pkg
pacman -Q | grep <pkg>
```

I want to learn about something:
```
sudo pacman -S man-db
man <pkg>
```

I want to have a clean system:
```
pacman -S pacman-contrib
paccache -r
checkupdates   
bash-completion 2.17.0-1 -> 2.17.0-2
mkinitcpio 40-3 -> 40-4
# visit archlinux.org/news ideally before updating
# limit AUR usage to strictly necessary
```

I have slow mirrors:
```
sudo reflector --protocol https --latest 20 --sort rate --save /etc/pacman.d/mirrorlist
sudo pacman -Sy
```
