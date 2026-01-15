# Alpha

> [!TIP]
> In the ISO, you are root by default. Use sudo or equivalent, if running from an existing system.

**0. Get internet access**

Ethernet cable is plug and play. (Skip section bellow)

Test: `ping -c 3 google.com`

**For Wifi**:
```
# check devices
$ ip link

$ iwctl station wlan0 connect "SSID"
# where SSID is the name of your wifi
# where wlan0 is your device name
# case sensitive and will prompt for password

$ nmcli dev wifi connect "SSID" -a
# alternative
```

**1. Get and run the source code**

Prep:
```
pacman-key --init
pacman -Sy archlinux-keyring git
pacman-key --populate archlinux 
```
Get source:
```
git clone https://github.com/h8d13/archinstoo
cd archinstoo/archinstall
```

**2. Then finally run the module** `archinstall`

`python -m archinstall [args]` try `-h` or `--help`

Some options are behind `--advanced` others help to skip.

There is also a `--script list` where you can make plugins for easily for `archinstoo`

**3. Enjoy your new system(s)**

Make your pizzas.

> You can create any profile in `archinstall/default_profiles/` following convention, which you can then use directly.
Or modify existing ones.

---

## Known issues

> **Issues with dependencies**

[ISO](https://archlinux.org/download/) is built 1st of each month.

> Do also note that the ISO has limited `cow_space`, running any form of `-Syu` or updating packages can trigger space errors/or read-only hook issues, and needs to be rebuilt with more space for certain breaking updates (especially ones with pacman hooks). Usually build a `1GB` ISO to test dev builds (vs the original `256M`). See [`ISOMOD`](./ISOMOD)

Check: 
```
. ./PKGBUILD && pacman -Qu "${depends[@]}"
# or the same with "${opt_depends[@]}"
```
Update:
```
. ./PKGBUILD && pacman -Sy --needed "${depends[@]}" 
# or the same with "${opt_depends[@]}"
```

The full list can be seen here [`PKGBUILD`](./PKGBUILD)

You can also use a `venv` and `pip install -e .` or for dev purposes: See [`RUN`](./RUN) to automate this.

## Testing

**Philosophy:** Simplify, No backwards-compat, Move fast.

To test fixes see: [Contributing](./.github/CONTRIBUTING.md) to see latest changes [Changelog](./.github/HISTORY.md)

The process would be the same with `git clone -b <branch> <url>`

## Building source from local

Modify what you like inside the repo, then:

`makepkg -Cf` force and clean for rebuilds.

`sudo pacman -U archinstoo-*.pkg.tar.zst` install the output file.

You can now use `archinstall` globally with this local version.

---
