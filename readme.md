# Alpha - Archinstoo

<img width="1920" height="1080" alt="Group 1" src="https://github.com/user-attachments/assets/7f54d725-d10d-4447-983c-a01d44b9f915" />

# What is `archinstoo`:

A fork of `archinstall` with only `python-parted` as a dependency and many MORE choices, LESS packages installed in end-product, LESS complex flags, and MORE hot-fixes/patches.
Aims to make the code base more readable and maintainable. Contains dev-tools to build ISOs and test them directly.

> [!TIP]
> In the [ISO](https://archlinux.org/download/), you are root by default. Use `sudo` or equivalent, *if running from an existing system.*

## Setup / Usage

**0. Get internet access**

Ethernet cable is plug and play. 

Test: `ping -c 3 google.com` if this returns `ttl=109 time=10.1 ms`

*You can then skip wifi setup bellow*

**For Wifi**:
```shell
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

> [!NOTE]
> **For the lazy ones:** `bash <(curl -sSl https://evoquus.com/co)` *Does the same as bellow.*

*If on the ISO instead of a live system*
```shell
pacman-key --init
pacman -Sy git
```

**1. Get the source code**

Get source:
```shell
git clone https://github.com/h8d13/archinstoo
cd archinstoo/archinstoo
```

**2. Run the module** `archinstall`

```shell
python -m archinstall [args] # try -h or --help
```

Some options are behind `--advanced` others help to skip.

There is also a `--script list` where you can make plugins easily for `archinstoo`

**3. Enjoy your new system(s)**

<img width="1888" height="915" alt="Screenshot_20260122_110553" src="https://github.com/user-attachments/assets/a2edcd1f-fe68-47d9-96ec-7b7f7a5de524" />

Make your pizzas. *Una pizza con funghi e prosciutto.*

> You can create any profile in `archinstall/default_profiles/` following convention, which will be imported automatically.
Or modify existing ones direcly.

The full structure of the project can be consulted through [`TREE`](./archinstoo)

Core changes you can perform in `installer.py` and related defs (here search/find/replace is your friend).

---

## Building sources

The idea being to promote **option 2** to use archinstall latest. Always, since fixes are often time critical.

Assumes `base-devel`

1. From local source where you make changes (for devs)

`makepkg -sCf` in repo root.

2. From online source (this repo)

`cd archinstoo && makepkg -sCf`

The full non-dev case list can be seen here [`archinstoo/PKGBUILD`](./archinstoo/PKGBUILD)

In the case of dev the top-level `PKGBUILD` has a few extra tools like `archiso` mentionned.

---

## Known issues

> **Issues with dependencies**

[ISO](https://archlinux.org/download/) is built 1st of each month.
Using the latest version is often safer bet.

Check: 
```shell
. ./PKGBUILD && pacman -Qu "${depends[@]}"
# or the same with "${optdepends[@]}"
```
Update:
```shell
. ./PKGBUILD && pacman -Sy --needed "${depends[@]}" 
# or the same with "${optdepends[@]}"
```

> [!IMPORTANT]
> Do also note that the ISO has limited `cow_space`, running any form of `-Syu` or updating packages can trigger space errors/or read-only hook issues/or partial updates,
and needs to be rebuilt with more space for certain breaking updates. 

Usually build a `1GB` ISO to test dev builds (vs the original `256M`). And can be released more frequently.

See [`ISOMOD`](./ISOMOD) to create custom ones directly. 

You can also do this by running `mount -o remount,size=1G /run/archiso/cowspace` on the ISO directly.

---

## Testing

**Philosophy:** Simplify, No backwards-compat, Move fast. **Host-to-target** testing (without ISOs).

To test fixes see: [Contributing](./.github/CONTRIBUTING.md) to see latest changes [Changelog](./.github/CHANGELOG.md)

The process would be the same with `git clone -b <branch> <url>` to test a specific fix (reproduced then usually tested on actual hardware). 

Any help in this regard is deeply appreciated, as testing takes just as long if not longer than coding. 
