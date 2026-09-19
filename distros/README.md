# partstoob

Experimental ports `archinstoo` to run from **any Linux host** (not just Arch ISOs).

> Mostly tested from smallest **server type ISOs/cloud images**.

Not fully cooked since it takes a lot of time, but at least all deps should be correct.

Can be found bellow:

| Logo | Host | `arch-install-scripts` | `pacman` | Script | Tested |
|------|------|------------------------|----------|--------|--------|
| <img src="assets/deb_bw.svg" width="24" alt="Debian"> | Debian | V | V | [DEB](https://github.com/h8d13/archinstoo/tree/master/distros/DEB) | V |
| <img src="assets/nix_bw.svg" width="24" alt="Nix"> | Nix | V | V | [NIX](https://github.com/h8d13/archinstoo/blob/master/distros/flake.nix) | V |
| <img src="assets/alp_bw.svg" width="24" alt="Alpine"> | Alpine | V | V | [ALP](https://github.com/h8d13/archinstoo/tree/master/distros/ALP) | V |
| <img src="assets/fed_bw.svg" width="24" alt="Fedora"> | Fedora | V | V | [FED](https://github.com/h8d13/archinstoo/tree/master/distros/FED) | V |

For alpine ISOs: https://alpinelinux.org/downloads/ (See "Standard" ~400mb)

---

> "If it works on Alpine, it works anywhere."
> And this is true especially because of their [package-splits](https://wiki.alpinelinux.org/wiki/Creating_an_Alpine_package#subpackages)
> No `systemd`, no `glibc`.
