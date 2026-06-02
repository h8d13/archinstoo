# Alpha - Archinstoo

<img width="1920" height="1080" alt="Group 1" src="https://github.com/user-attachments/assets/7f54d725-d10d-4447-983c-a01d44b9f915" />

# What is `archinstoo`:

A fork of `archinstall` an operating system installer for [archlinux](https://archlinux.org). MORE choices, LESS packages installed in end-product, LESS complex flags, and MORE hot-fixes. *Aims to make the code base more readable, maintainable and modifiable by anyone*.

> [!TIP]
> In the [ISO](https://archlinux.org/download/), you are root by default and have some tools available.
> Use `sudo` or equivalent, *if running from an existing system.*

## Setup / Usage

[Newb-Corner](.github/NEWB_CORNER.md)

**0. Get internet access**
> [!NOTE]
> Ethernet cable is plug and play.

Test: `ping -c 3 google.com` if this returns `ttl=109 time=10.1 ms` 3 times...

*You can then skip wifi setup below*

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

*If on the ISO instead of a live system*
```shell
pacman-key --init
pacman -Syy
pacman -S git python
```

### **1. Get the source code**

```shell
git clone --depth 1 https://github.com/h8d13/archinstoo
cd archinstoo/archinstoo
```

### **2. Run the code**

```shell
python -m archinstoo [args] # try -h or --help
# some options are behind --advanced
```

### **3. Enjoy your new system(s)**

<img width="1888" height="915" alt="Screenshot_20260122_110553" src="https://github.com/user-attachments/assets/a2edcd1f-fe68-47d9-96ec-7b7f7a5de524" />

Make your pizzas. *Una pizza con funghi e prosciutto.*

> Alternatively: There are 2 wrappers/helpers from the repo root: `./RUN`(regular) and `./DEV`(advanced) which perform similar steps to 1 and 2.

---

## Modify/Extend

> You can create any profile in `archinstoo/default_profiles/` following convention, which will be imported automatically.
Or modify existing ones directly. Can also see here for [examples](./archinstoo/examples)

You can make plugins easily `--script list` for `archinstoo`, anything inside `scripts/` is also imported.

```yaml
Available options:
              [*] requires root
    count
    mirror
    size
    format    [*]
    guided    [*] < DEFAULT
    live      [*]
    minimal   [*]
    packages  [*]
    rescue    [*]
```

The full structure of the project can be consulted through [`TREE`](./archinstoo)

Core changes you can perform in `installer.py` and related defs (here search/find/replace is your friend).

A `man` page is also available `man -l docs/archinstoo.1`

## Use cases

See [Headless](./.github/HEADLESS.md) for example server install to play minecraft/run tailscale nodes.

See [Multi-boot](./.github/MULTI_BOOT.md) for example to boot multiple OSes.

See [Security](./.github/SECURITY.md) for hardening installs/best practices.

See [Build-ISOs](./.github/BUILD_ISOS.md) to create your own install mediums.

See [Cachy-Kernels](./.github/CACHY_KERNELS.md) for swapping to their kernels post-install.

See [Out-of-Tree](./.github/OUT_OF_TREE.md) for example install on unsupported hardware. (Older nVIDIA, Realtek, ...)

See [ARM-Support](./.github/ARM_SUPPORT.md) for example install on Raspi 5-b.

See all other docs: [.github](./.github/) and [ArchWiki](https://wiki.archlinux.org/title/Main_page)

## Testing

**Host-to-target:** testing (without ISOs) Here you will need more [dependencies](./archinstoo/PKGBUILD)

See historical/latest changes [Changelog](./.github/CHANGELOG.md) and [Troubleshooting](./.github/TROUBLESHOOT.md)

The process would be the same with `git clone -b <branch> <url>` to test a specific fix. Usually reproduced then tested on **actual/appropriate hardware.**

> Any help in this regard is deeply appreciated, as testing takes just as long, if not longer, than coding.

Accurate reports/PRs will be addressed in a timely manner: [Issues](https://github.com/h8d13/archinstoo/issues) and [Contributing](./.github/CONTRIBUTING.md)

---

## Building sources

The idea being to promote **option 2** to use archinstoo latest non-dev. Always, since fixes are often time critical.

1. For **DEV** top-level `PKGBUILD` has extra tools like `archiso`, `pacman-contrib` and `nvchecker`.

2. For **non-dev** can be seen here [`archinstoo/PKGBUILD`](./archinstoo/PKGBUILD) uses the repo without it's top part from git.

See [`archinstall`](https://github.com/archlinux/archinstall) and thanks to the many original contributors.

**Philosophy:** Simplify, No backwards-compat, Move fast (even if it means breaking and fixing). 

See [Philosophy](./.github/PHILOSOPHY.md) 
