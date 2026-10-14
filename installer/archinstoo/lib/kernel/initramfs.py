from typing import TYPE_CHECKING

from archinstoo.lib.exceptions import SysCallError
from archinstoo.lib.output import debug, info, log, warn

if TYPE_CHECKING:
	from pathlib import Path

	from archinstoo.lib.installer import Installer

LVM = 'lvm2'  # the package; its dracut module is 'lvm'
DRACUT_CONF = 'etc/dracut.conf.d/90-fedinstoo.conf'


class Initramfs:
	# what the install puts into dracut.conf.d before the kernel is installed:
	# the kernel's posttrans runs kernel-install, whose dracut plugin builds
	# the image from it. Hostonly (Fedora's default) already picks up what
	# the mounted layout needs; these pin it for the layouts it cannot see
	# through a chroot (keyfile unlock, assembled arrays)
	# anaconda/pyanaconda/modules/storage/bootloader/utils.py:265-268
	def __init__(self) -> None:
		self.modules: list[str] = []
		self.drivers: list[str] = []
		self.files: list[str] = []

	def _add_module(self, module: str) -> None:
		if module not in self.modules:
			debug(f'Adding dracut module {module}')
			self.modules.append(module)

	def add_lvm(self) -> None:
		self._add_module('lvm')

	def add_raid(self) -> None:
		self._add_module('mdraid')

	def add_encrypt(self) -> None:
		# systemd-cryptsetup in the initramfs: reads /etc/crypttab, which the
		# crypt module copies in alongside
		self._add_module('crypt')

	def add_fido2(self) -> None:
		self._add_module('fido2')

	def add_resume(self) -> None:
		# hostonly only takes it when resume= is on the cmdline or the build
		# host's /sys/power/resume is set; UEFI hibernation needs neither
		# (systemd records the swapfile in HibernateLocation), so ask for it
		self._add_module('resume')

	def write_conf(self, target: Path) -> None:
		lines = []
		if self.modules:
			lines.append(f'add_dracutmodules+=" {" ".join(self.modules)} "')
		if self.drivers:
			lines.append(f'add_drivers+=" {" ".join(self.drivers)} "')
		if self.files:
			lines.append(f'install_items+=" {" ".join(self.files)} "')

		conf = target / DRACUT_CONF
		conf.parent.mkdir(parents=True, exist_ok=True)
		conf.write_text(''.join(f'{line}\n' for line in lines))
		debug(f'{conf}:\n' + '\n'.join(lines))

	def build(self, installation: Installer) -> bool:
		# every installed kernel, same as its posttrans would
		self.write_conf(installation.target)
		info('Building initramfs...', step=True)

		try:
			installation.arch_chroot('dracut --regenerate-all --force', peek_output=True)
			return True
		except SysCallError as e:
			warn(f'dracut failed: {e}')
			if e.worker_log:
				log(e.worker_log.decode())
			return False
