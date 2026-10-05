from typing import TYPE_CHECKING

from archinstoo.lib.kernel.sysctl import write_sysctl
from archinstoo.lib.models.swap import ZramAlgorithm
from archinstoo.lib.models.sysctl import ZRAM_CONF, ZRAM_DEFAULTS
from archinstoo.lib.output import info

if TYPE_CHECKING:
	from archinstoo.lib.installer import Installer

__zram_packages__ = ['zram-generator']


def setup_zram(installation: Installer, algo: ZramAlgorithm, recomp_algo: ZramAlgorithm | None) -> None:
	info('Setting up swap on zram')
	installation.pacman.strap(__zram_packages__)

	with (installation.target / 'etc/systemd/zram-generator.conf').open('w') as zram_conf:
		zram_conf.write('[zram0]\n')
		zram_conf.write('zram-size = ram / 2\n')
		if algo != ZramAlgorithm.Default:
			comp_line = algo.value
			if recomp_algo:
				comp_line += f' {recomp_algo.value} (type=idle)'
			zram_conf.write(f'compression-algorithm = {comp_line}\n')

	# tuning that only holds with zram as the swap device, so it ships with it
	write_sysctl(installation.target, ZRAM_CONF, ZRAM_DEFAULTS)
	installation.enable_service('systemd-zram-setup@zram0')
