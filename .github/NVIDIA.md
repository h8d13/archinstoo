# Nvidia stuff

## Older cards 

From the [wiki](https://wiki.archlinux.org/title/NVIDIA) you can gather that if your card is below 16XX[^1]

You will need the AUR. See [this](./OUT_OF_TREE.md) 

### Example on 1050Ti 

0. Launch `archinstoo` with `--advanced` flag
1. Skip `Graphics Driver` and toggle kernel headers in `kernel` menu.
2. Add to AUR packages `nvidia-580xx-utils`
3. Add to additional packages `libva-nvidia-driver`

And you are done !

## Recent cards

Is much easier: The only main thing to understand is that if you pick a kernel that is not mainline `linux` you will need `dkms`. (This is handled automatically).
So using mainline kernel makes `pacman` updates easier/faster.

[^1]: Arch news drop pascal support [link](https://archlinux.org/news/nvidia-590-driver-drops-pascal-support-main-packages-switch-to-open-kernel-modules/)
