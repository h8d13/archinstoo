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

> [!IMPORTANT]
> Do also note that the ISO has limited `cow_space`, running any form of `-Syu` or updating packages can trigger space errors/or read-only hook issues/or partial updates,
and needs to be rebuilt with more space for certain breaking updates. 

Usually build a `1GB` ISO to test dev builds (vs the original `256M`). And can be released more frequently.

See [`ISOMOD`](./ISOMOD) to create custom ones directly. 

You can also do this by running `mount -o remount,size=1G /run/archiso/cowspace` on the ISO directly.

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