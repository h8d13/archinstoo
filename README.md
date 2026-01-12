# Alpha

0. Get internet access

Ethernet cable is plug and play.

Test: `ping -c 3 google.com`

**For Wifi**:
```
iwctl station wlan0 connect "SSID"
# where SSID is the name of your wifi
# where wlan0 is your device name
# case sensitive and will prompt for password

nmcli dev wifi connect "SSID" -a
# you can also use nmcli if you prefer
```

1. Get and run the source code or specific branch/fork

```
pacman-key --init
pacman -Sy archlinux-keyring git
git clone -b alpha https://github.com/h8d13/archinstoo
cd archinstoo
```

Check deps are up to date (ISO is built 1st of each month)

`. PKGBUILD && pacman -Sy --needed ${depends[@]}`

Then finally run the archinstall module

`python -m archinstall [args]`

2. Enjoy your new system(s)

---

**Philosophy:** Simplify, No backwards-compat, Move fast.