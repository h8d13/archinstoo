# Alpha - Archinstoo

<img width="1920" height="1080" alt="Group 1" src="https://github.com/user-attachments/assets/7f54d725-d10d-4447-983c-a01d44b9f915" />

## What is `archinstoo`:

A fork of `archinstall` an operating system installer for [archlinux](https://archlinux.org).

> MORE choices, LESS packages in end-product, LESS complex flags, and MORE hot-fixes.

*Aims to make the code base more readable, maintainable and modifiable by anyone*.

> [!TIP]
> In the [ISO](https://archlinux.org/download/), you are root by default.
> Use `sudo` or equivalent, *when from an existing system.*

## Setup / Usage

### **1. Get internet access**
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

### **2. Prep**

*If on the ISO instead of a live system*
```shell
pacman-key --init
pacman -Syy git
```

### **3. Get the source code**

```shell
git clone https://github.com/h8d13/archinstoo
```

### **4. Run the code**

```shell
cd archinstoo/archinstoo
python -m archinstoo [args] # try -h or --help
# some options are behind --advanced
```

### **5. Enjoy your new system(s)**

<img width="1278" height="800" alt="Screenshot_20260608_165700" src="https://github.com/user-attachments/assets/3ac69a5c-31f6-4132-93e5-26bc0555768d" />

Make your pizzas. *Una pizza con funghi e prosciutto.*

> [!TIP]
> **Alternatively:** There are wrappers/helpers (which perform similar step to 4) from the **repo root**:

```shell
./RUN # regular
./DEV # advanced
```

---

## Modify/Extend

> You can create any profile in `archinstoo/default_profiles/` following convention, which will be imported automatically.
Or modify existing ones directly. Can also see here for [examples](https://github.com/h8d13/archinstoo/tree/master/archinstoo/examples)

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

The full structure of the project can be consulted through [`TREE`](https://github.com/h8d13/archinstoo/tree/master/archinstoo)

Core changes you can perform in `installer.py` and related defs (here search/find/replace is your friend).

A `man` page is also available `man -l docs/archinstoo.1`

### Use cases

See [Newb-Corner](https://github.com/h8d13/archinstoo/blob/master/.github/NEWB_CORNER.md) if you're just starting out with Arch.

See [Headless](https://github.com/h8d13/archinstoo/blob/master/.github/HEADLESS.md) for example server install to play minecraft/run tailscale nodes.

See [Multi-Boot](https://github.com/h8d13/archinstoo/blob/master/.github/MULTI_BOOT.md) for example to boot multiple OSes.

See [Security](https://github.com/h8d13/archinstoo/blob/master/.github/SECURITY.md) for hardening installs/best practices.

See [Build-ISOs](https://github.com/h8d13/archinstoo/blob/master/.github/BUILD_ISOS.md) to create your own install mediums.

See [Cachy-Kernels](https://github.com/h8d13/archinstoo/blob/master/.github/CACHY_KERNELS.md) for swapping to their kernels post-install.

See [Out-of-Tree](https://github.com/h8d13/archinstoo/blob/master/.github/OUT_OF_TREE.md) for example install on unsupported hardware. (Older nVIDIA, Realtek, ...)

See [ARM-Support](https://github.com/h8d13/archinstoo/blob/master/.github/ARM_SUPPORT.md) for example install on Raspi 5-b.

See all other docs: [.github](https://github.com/h8d13/archinstoo/tree/master/.github) and [ArchWiki](https://wiki.archlinux.org/title/Main_page)

### Testing

**Host-to-target:** testing (without ISOs) Here you will need more [dependencies](https://github.com/h8d13/archinstoo/blob/master/archinstoo/PKGBUILD)

See historical/latest changes [Changelog](https://github.com/h8d13/archinstoo/blob/master/.github/CHANGELOG.md)

The process would be the same with `git clone -b <branch> <url>` to test a specific fix. Usually reproduced then tested on **actual/appropriate hardware.**

> Any help in this regard is deeply appreciated, as testing takes just as long, if not longer, than coding.

Accurate reports/PRs will be addressed in a timely manner: [Issues](https://github.com/h8d13/archinstoo/issues) and [Contributing](https://github.com/h8d13/archinstoo/blob/master/.github/CONTRIBUTING.md)

**Philosophy:** Simplify, No backwards-compat, Move fast (even if it means breaking and fixing).

See [Philosophy](https://github.com/h8d13/archinstoo/blob/master/.github/PHILOSOPHY.md)

See [Troubleshooting](https://github.com/h8d13/archinstoo/blob/master/.github/TROUBLESHOOT.md)

---

## Building sources

The idea being to promote **option 2** to use archinstoo latest non-dev. Always, since fixes are often time critical.

1. For **DEV** top-level `PKGBUILD` has extra tools like `archiso`, `pacman-contrib` and `nvchecker`.

2. For **non-dev** see [`archinstoo/PKGBUILD`](https://github.com/h8d13/archinstoo/blob/master/archinstoo/PKGBUILD) uses the repo without its top part from git.

See [`archinstall`](https://github.com/archlinux/archinstall) and thanks to the many original contributors.

See [mirror](https://gitlab.archlinux.org/h8d13/archinstoo/) for a copy of this repo, not on GitHub.

---

<div align="center">

Made with ♡

[Star this repo](https://github.com/h8d13/archinstoo) · [Bugs/Features](https://github.com/h8d13/archinstoo/issues/new) · [Discussions](https://github.com/h8d13/archinstoo/discussions)

</div>
