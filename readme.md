# Alpha - Archinstoo

<img width="1920" height="1080" alt="Group 1" src="https://github.com/user-attachments/assets/7f54d725-d10d-4447-983c-a01d44b9f915" />

## What is `archinstoo`

An operating system installer (and tools) for [archlinux](https://archlinux.org).

> [!TIP]
> In the [ISO](https://archlinux.org/download/), you are root by default.
> Use `sudo` or equivalent, *when from an existing system.*

## Setup / Usage

### 0. Keymap

On the ISO, you can `loadkeys <somekblayout>`

You can also check available ones:

`localectl list-keymaps` otherwise defaults to `us`.

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
cd archinstoo/installer
python -m archinstoo [args] # try -h or --help
# some options are behind --advanced
```

### **5. Enjoy your new system(s)**

<img width="1278" height="800" alt="Screenshot_20260608_165700" src="https://github.com/user-attachments/assets/3ac69a5c-31f6-4132-93e5-26bc0555768d" />

Make your pizzas. *Una pizza con funghi e prosciutto.*

See [Newb-Corner](https://github.com/h8d13/archinstoo/blob/master/.github/NEWB_CORNER.md) if you're just starting out with Arch.

> [!TIP]
> **Alternatively:** There are wrappers/helpers (which perform similar step to 4) from the **repo root**:

```shell
./RUN # regular
./DEV # advanced
```

---

## Modify/Extend

> You can create any profile in [`archinstoo/default_profiles/`](https://github.com/h8d13/archinstoo/tree/master/installer/archinstoo/default_profiles) following convention, which will be imported automatically.
Or modify existing ones directly. Can also see here for [examples](https://github.com/h8d13/archinstoo/tree/master/installer/examples)

You can make plugins easily `--script list` for `archinstoo`, anything inside [`scripts/`](https://github.com/h8d13/archinstoo/tree/master/installer/archinstoo/scripts) is also imported.

```yaml
Available options:
              [*] requires root
    count
    mirror
    passwd
    size
    format    [*]
    guided    [*] < DEFAULT
    live      [*]
    minimal   [*]
    packages  [*]
    rescue    [*]
```

The full structure of the project can be consulted through [`TREE`](https://github.com/h8d13/archinstoo/tree/master/installer)

Install steps are ordered in [`installer.py`](https://github.com/h8d13/archinstoo/blob/master/installer/archinstoo/lib/installer.py) here search/find/replace is your friend.
A `man` page is also available `man -l installer/docs/archinstoo.1`

### Use cases / Docs

See the full documentation on [mkdocs](https://h8d13.github.io/archinstoo/) generated from this repo.

### Testing

**Host-to-target:** testing (without ISOs) here you will need more [dependencies](https://github.com/h8d13/archinstoo/blob/master/installer/PKGBUILD).

See historical/latest changes [Changelog](https://github.com/h8d13/archinstoo/blob/master/.github/CHANGELOG.md)

The process would be the same with `git clone -b <branch> <url>` to test a specific fix. Usually reproduced then tested on **actual/appropriate hardware.**

> Any help in this regard is deeply appreciated, as testing/digging takes just as long as writing code. Accurate reports/PRs will be addressed in a timely manner:
> [PRs](https://github.com/h8d13/archinstoo/pulls), [Issues](https://github.com/h8d13/archinstoo/issues) and [Contributing](https://github.com/h8d13/archinstoo/blob/master/.github/CONTRIBUTING.md)

**Philosophy:** Simplify, No backwards-compat, Move fast (even if it means breaking and fixing).
[More...](https://github.com/h8d13/archinstoo/blob/master/.github/PHILOSOPHY.md)

---

## Building sources

>[!NOTE]
> For **DEV** top-level `PKGBUILD` has extra tools like `archiso`, `pacman-contrib` and `nvchecker`.
> For **non-dev** see [`installer/PKGBUILD`](https://github.com/h8d13/archinstoo/blob/master/installer/PKGBUILD) uses the repo without its top part from git.

But it is recommended to use latest from git `master` instead.

See [`archinstall`](https://github.com/archlinux/archinstall) and thanks to the many original contributors. And the [arch-wiki](https://wiki.archlinux.org/title/Main_page).

See [mirror](https://gitlab.archlinux.org/h8d13/archinstoo/) for a copy of this repo, not hosted on GitHub.

---

<div align="center" markdown>

Made with ♡

[Documentation](https://h8d13.github.io/archinstoo/) · [Star this repo](https://github.com/h8d13/archinstoo) · [Bugs/Features](https://github.com/h8d13/archinstoo/issues/new) · [Discussions](https://github.com/h8d13/archinstoo/discussions)

</div>
