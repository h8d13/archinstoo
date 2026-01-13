# Alpha

**0. Get internet access**

Ethernet cable is plug and play.

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

**1. Get and run the source code or specific branch/fork**

Prep:
```
pacman-key --init
pacman -Sy archlinux-keyring git
pacman-key --populate archlinux 
```
Get source:
```
git clone -b alpha https://github.com/h8d13/archinstoo
cd archinstoo
```

Check deps are up to date ([ISO](https://archlinux.org/download/) is built 1st of each month)

`. PKGBUILD && pacman -Sy --needed ${depends[@]}`

**2. Then finally run the module** `archinstall`

`python -m archinstall [args]` try `-h` or `--help`

Make your pizza.

**3. Enjoy your new system(s)**

---

**Philosophy:** Simplify, No backwards-compat, Move fast.