import re
from typing import TYPE_CHECKING

from archinstoo.lib.exceptions import SysCallError
from archinstoo.lib.output import debug, info, log, warn

if TYPE_CHECKING:
	from pathlib import Path

	from archinstoo.lib.installer import Installer


class Initramfs:
	# what the install puts into mkinitcpio.conf before building the image.
	# The lists are edited in place by the installer as the layout demands
	# (sd-encrypt, lvm2, bcachefs, keyfiles); build() writes them and runs
	def __init__(self) -> None:
		self.modules: list[str] = []
		self.binaries: list[str] = []
		self.files: list[str] = []
		# systemd flavour of the stock hook order
		self.hooks: list[str] = [
			'base',
			'systemd',
			'autodetect',
			'microcode',
			'modconf',
			'kms',
			'keyboard',
			'sd-vconsole',
			'block',
			'filesystems',
			'fsck',
		]

	def write_conf(self, target: Path) -> None:
		with (target / 'etc/mkinitcpio.conf').open('r+') as mkinit:
			content = mkinit.read()
			content = re.sub(r'\nMODULES=(.*)', f'\nMODULES=({" ".join(self.modules)})', content)
			content = re.sub(r'\nBINARIES=(.*)', f'\nBINARIES=({" ".join(self.binaries)})', content)
			content = re.sub(r'\nFILES=(.*)', f'\nFILES=({" ".join(self.files)})', content)
			content = re.sub(r'\nHOOKS=(.*)', f'\nHOOKS=({" ".join(self.hooks)})', content)
			mkinit.seek(0)
			mkinit.truncate()
			mkinit.write(content)

		debug(f'mkinitcpio.conf HOOKS=({" ".join(self.hooks)}) MODULES=({" ".join(self.modules)}) FILES=({" ".join(self.files)})')

	def build(self, installation: Installer, flags: list[str]) -> bool:
		self.write_conf(installation.target)
		info('Building initramfs...', step=True)

		try:
			installation.arch_chroot(f'mkinitcpio {" ".join(flags)}', peek_output=True)
			return True
		except SysCallError as e:
			warn(f'mkinitcpio failed: {e}')
			if e.worker_log:
				log(e.worker_log.decode())
			return False
