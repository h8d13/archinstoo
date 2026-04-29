from pathlib import Path
from typing import Final

from archinstoo.lib.linux_path import LPath

ARCHISO_MOUNTPOINT: Final = Path('/run/archiso/airootfs')
MIRRORLIST: Final = LPath('/etc/pacman.d/mirrorlist')
PACMAN_CONF: Final = LPath('/etc/pacman.conf')
ARTIFACTS_STORE: Final = LPath('etc/archinstoo.d')
