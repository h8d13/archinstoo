# Troubleshooting

## Known issues

### **Issues with dependencies**

Arch's [ISO](https://archlinux.org/download/) is built 1st of each month.
> Using the **latest version** is often safer bet.

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

For the lazy ones: `./DEV -h2t` or with optionals `./DEV -h2t -o`

### **Issues with signatures/keyring**

> Check system BIOS clock / timezone
```shell
killall gpg-agent
rm -rf /etc/pacman.d/gnupg
pacman-key --init
pacman-key --populate
pacman -Sy archlinux-keyring
```
Then run `archinstoo` [Back to Step 1](https://github.com/h8d13/archinstoo?tab=readme-ov-file#1-get-the-source-code)

https://github.com/archlinux/archinstall/issues/4018
https://github.com/archlinux/archinstall/issues/2213

---
