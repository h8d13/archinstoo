# Hybrid Graphics - iGPU + dGPU

Many laptops seem to have an integrated graphics card + dedicated.
No preset covers both GPUs: pick `Custom` under `Graphics driver` and tick the packages of each,
for instance `nvidia-open` + `libva-nvidia-driver` next to `mesa` + `vulkan-intel`.
A single-vendor preset leaves the other GPU unaccelerated.

> [!TIP]
> Offload tools are opt-in, install what fits after the first boot:
> [`switcheroo-control`](https://archlinux.org/packages/extra/x86_64/switcheroo-control/) (desktop "launch on discrete GPU"),
> [`nvidia-prime`](https://archlinux.org/packages/extra/any/nvidia-prime/) (`prime-run`) or equivalent [`asusctl`](https://wiki.archlinux.org/title/Asusctl) for instance.
> More information is also available on this page: [Wiki PRIME](https://wiki.archlinux.org/title/PRIME).

Presets and the `Custom` package list can be found in this [code path](https://github.com/h8d13/archinstoo/blob/master/installer/archinstoo/lib/models/graphics.py)

In order to check your dGPU is running fine: `nvidia-smi`

Some other useful debug commands:

- `lspci -k | grep -A3 "VGA"`
- `lsmod | grep "nvidia"`
- `sudo dmesg | grep -iE 'nvrm|nvidia|nouveau'`

In many cases you'll need to either add kernel params or check BIOS settings.

See [issues/244](https://github.com/h8d13/archinstoo/issues/244) for reference.
