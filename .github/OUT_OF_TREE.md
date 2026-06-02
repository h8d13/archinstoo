# AUR support

For some hardware using the AUR for drivers is inevitable

Hence why you can now use `--advanced` to get AUR support built-in 
> Uses a modified [`grimaur`](../archinstoo/archinstoo/lib/grimaur.py) *during install*. As far as I known not many installers allow for this.

=> Make sure **to toggle kernel headers** from your desired variant(s) if you are building DKMS modules.

*For obvious reason another disclaimer here* is to make sure you know to trust what you are installing.
Especially with the automated nature of the installs and that sufficiently harden a machine for your use cases and limit AUR usage.

Directly supported [hardware](../archinstoo/archinstoo/lib/hardware.py) can all be seen here through detection.

See also: [nVIDIA](./NVIDIA.md)
