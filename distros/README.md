# partstoob

Experimental ports `archinstoo` to run from **any Linux host** (not just Arch ISOs).

> Mostly tested from smallest **server type ISOs**.

Not fully cooked since it takes a lot of time, but at least all deps should be correct.

Can be found bellow:

| Host | `arch-install-scripts` | `pacman` | Script | Tested |
|------|------------------------|----------|--------|--------|
| Debian | V | V | [DEB](./DEB) | X |
| Nix | V | V | [NIX](./flake.nix) | X |
| Alpine | V | V | [ALP](./ALP) | V |

---

Missing X? > Fetch from Y or fallback to Z (usually trying to keep in line with upstream sources).

> "If it works on Alpine, it works anywhere."
> And this is true especially because of their [package-splits](https://wiki.alpinelinux.org/wiki/Creating_an_Alpine_package#subpackages)
> No `systemd`, no `glibc`
