# Alpha - Archinstoo

<img width="1920" height="1080" alt="Group 1" src="https://github.com/user-attachments/assets/7f54d725-d10d-4447-983c-a01d44b9f915" />

# What is `archinstoo`:

A fork of `archinstall` with only `python-parted` as a dependency, many MORE choices, LESS packages installed in end-product, LESS complex flags, and MORE hot-fixes/patches. *Aims to make the code base more readable, maintainable and modifiable by anyone*.

> [!TIP]
> In the [ISO](https://archlinux.org/download/), you are root by default. Use `sudo` or equivalent, *if running from an existing system.*

## Setup / Usage

[Newb-Corner](.github/NEWB_CORNER.md)

**0. Get internet access**

Ethernet cable is plug and play. 

Test: `ping -c 3 google.com` if this returns `ttl=109 time=10.1 ms` 3 times...

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

### **1. Get the source code**

Get source:
```shell
git clone --depth 1 https://github.com/h8d13/archinstoo
cd archinstoo/archinstoo
```

### **2. Run the module** `archinstall`

```shell
python -m archinstall [args] # try -h or --help
# some options are behind --advanced
```

### **3. Enjoy your new system(s)**

<img width="1888" height="915" alt="Screenshot_20260122_110553" src="https://github.com/user-attachments/assets/a2edcd1f-fe68-47d9-96ec-7b7f7a5de524" />

Make your pizzas. *Una pizza con funghi e prosciutto.*

> You can create any profile in `archinstall/default_profiles/` following convention, which will be imported automatically.
Or modify existing ones direcly. Can also see here for [examples](./archinstoo/examples)

You can make plugins easily `--script list` for `archinstoo`, anything inside `scripts/` is also imported. 

The full structure of the project can be consulted through [`TREE`](./archinstoo)

Core changes you can perform in `installer.py` and related defs (here search/find/replace is your friend).

## Use cases

See [Headless](./.github/HEADLESS.md) for example server install to play minecraft.

See [Out-of-Tree](./.github/OUT-OF-TREE.md) for an example install with unsupported hardware.

## Testing

**Philosophy:** Simplify, No backwards-compat, Move fast. **Host-to-target** testing (without ISOs) [Philosophy](./.github/PHILOSOPHY.md).

To test fixes see: [Contributing](./.github/CONTRIBUTING.md) to see historical/latest changes [Changelog](./.github/CHANGELOG.md) and [Troubleshooting](./.github/TROUBLESHOOT.md) 

The process would be the same with `git clone -b <branch> <url>` to test a specific fix.

Usually reproduced then tested on actual/appropriate hardware. 

Any help in this regard is deeply appreciated, as testing takes just as long if not longer than coding. 

---

## Building sources

The idea being to promote **option 2** to use archinstall latest. Always, since fixes are often time critical.

1. In case of dev the top-level `PKGBUILD` has a few extra tools like `archiso` mentionned.

2. In case of non-dev case list can be seen here [`archinstoo/PKGBUILD`](./archinstoo/PKGBUILD)

---
