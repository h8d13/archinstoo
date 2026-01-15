# Alpha

> [!TIP]
> In the ISO, you are root by default. Use sudo or equivalent, if running from an existing system.

**0. Get internet access**

Ethernet cable is plug and play. 

Test: `ping -c 3 google.com` if this returns `ttl=109 time=10.1 ms`

*You can then skip wifi setup bellow*

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

**0.1. Prep**

*If on the ISO instead of a live system*
```
pacman-key --init
pacman -Sy git
```

**1. Run the source code**

Get source:
```
git clone https://github.com/h8d13/archinstoo
cd archinstoo/archinstoo
```

**2. Then finally run the module** `archinstall`

`python -m archinstall [args]` try `-h` or `--help`

Some options are behind `--advanced` others help to skip.

There is also a `--script list` where you can make plugins easily for `archinstoo`

**3. Enjoy your new system(s)**

Make your pizzas. Una pizza con funghi e prosciutto.

> You can create any profile in `archinstall/default_profiles/` following convention, which will be imported automatically.
Or modify existing ones direcly.

The full structure of the project can be consulted through [`TREE`](./archinstoo)

Core changes you can perform in `installer.py` and related defs (here search/find/replace is your friend).

## Building sources

Assumes `base-devel`

1. From local source where you make changes

`makepkg -sCf` in repo root.

2. From online source (this repo)

`cd archinstoo && makepkg -sCf`

> You can also get this file from [releases](https://github.com/h8d13/archinstoo/releases/) page

`sudo pacman -U archinstoo-*.pkg.tar.zst` install directly fromn where you have the tar file.

You can now use `archinstall` anyway you like.

---

## Known issues

> **Issues with dependencies**

[ISO](https://archlinux.org/download/) is built 1st of each month.
Using the latest version is often safer bet.

The full non-dev case list can be seen here [`archinstoo/PKGBUILD`](./archinstoo/PKGBUILD)
In the case of dev the top-level `PKGBUILD` has a few extra tools like `archiso` mentionned.

Check: 
```
. ./PKGBUILD && pacman -Qu "${depends[@]}"
# or the same with "${optdepends[@]}"
```
Update:
```
. ./PKGBUILD && pacman -Sy --needed "${depends[@]}" 
# or the same with "${optdepends[@]}"
```

You can also use a `venv` and `pip install -e ./archinstoo` or for dev purposes: See [`RUN`](./RUN) to automate this.

> Do also note that the ISO has limited `cow_space`, running any form of `-Syu` or updating packages can trigger space errors/or read-only hook issues, and needs to be rebuilt with more space for certain breaking updates. Usually build a `1GB` ISO to test dev builds (vs the original `256M`). See [`ISOMOD`](./ISOMOD)

## Testing

**Philosophy:** Simplify, No backwards-compat, Move fast.

To test fixes see: [Contributing](./.github/CONTRIBUTING.md) to see latest changes [Changelog](./.github/HISTORY.md)

The process would be the same with `git clone -b <branch> <url>`


