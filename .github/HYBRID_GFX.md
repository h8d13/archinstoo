# Hybrid Graphics - iGPU + dGPU

Many laptops seem to have an integrated graphics card + dedicated.
For this case: certain utilites are added through the `Custom` option in `Graphics driver`

You would still need to known if the iGPU is `amd` or `intel` in the common cases.

Defaults install: `switcheroo-control` and `vulkan-mesa-layers`.

> [!TIP]
> Other tools like `nvidia-prime` or equivalent [`asusctl`](https://wiki.archlinux.org/title/Asusctl) for instance.
> More information is also available on this page: [Wiki PRIME](https://wiki.archlinux.org/title/PRIME).

Hardware detection can be found in this [code path](https://github.com/h8d13/archinstoo/blob/master/installer/archinstoo/lib/hardware.py)

