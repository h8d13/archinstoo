# Alpha

0. Get internet access

Ethernet cable is plug and play
```
iwctl station wlan0 connect "SSID"
# where SSID is the name of your wifi
# case sensitive and will prompt for password
```

Test: `ping -c 3 google.com`

1. Get and run the source code

```
pacman-key --init
pacman -Sy git
git clone -b alpha https://github.com/h8d13/archinstoo
cd archinstoo
python -m archinstall [args]
```

2. Enjoy your new system
