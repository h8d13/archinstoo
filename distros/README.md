# partstoob

Experimental ports `archinstoo` to run from **any Linux host** (not just Arch ISOs).

> Mostly tested from smallest **server type ISOs/cloud images**.

Not fully cooked since it takes a lot of time, but at least all deps should be correct.

Can be found bellow:

| Host | `arch-install-scripts` | `pacman` | Script | Tested |
|------|------------------------|----------|--------|--------|
| Debian | V | V | [DEB](https://github.com/h8d13/archinstoo/tree/master/distros/DEB) | X |
| Nix | V | V | [NIX](https://github.com/h8d13/archinstoo/blob/master/distros/flake.nix) | X |
| Alpine | V | V | [ALP](https://github.com/h8d13/archinstoo/tree/master/distros/ALP) | V |
| Fedora | V | V | [FED](https://github.com/h8d13/archinstoo/tree/master/distros/FED) | V |

For alpine ISOs: https://alpinelinux.org/downloads/ (See "Standard" ~400mb)

Fedora ships both halves itself and its python is already 3.14, so `FED` is a
single `dnf` line. Its installer ISO carries no package manager at all, so test
from the Cloud Base qcow2 instead (~550mb, see `./TSER` for the cloud-init bit).

---

> "If it works on Alpine, it works anywhere."
> And this is true especially because of their [package-splits](https://wiki.alpinelinux.org/wiki/Creating_an_Alpine_package#subpackages)
> No `systemd`, no `glibc`.
