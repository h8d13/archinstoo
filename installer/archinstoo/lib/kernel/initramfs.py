import re
from typing import TYPE_CHECKING

from archinstoo.lib.exceptions import SysCallError
from archinstoo.lib.output import debug, info, log, warn

if TYPE_CHECKING:
	from pathlib import Path

	from archinstoo.lib.installer import Installer

LVM = 'lvm2'  # package and mkinitcpio hook share the name


class Initramfs:
	# what the install puts into mkinitcpio.conf before building the image.
	# The add_*/drop_* methods reorder the lists as the layout demands
	# (sd-encrypt, lvm2, bcachefs); keyfiles append to files directly.
	# build() writes them and runs mkinitcpio
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

	def add_lvm(self) -> None:
		# after block so the volume group's device is online before lvm2
		# activates it; add_encrypt(before=LVM) then slots sd-encrypt in
		# between, the order the wiki gives for LVM on LUKS
		debug(f'Inserting {LVM} hook before filesystems')
		self.hooks.insert(self.hooks.index('filesystems'), LVM)

	def add_encrypt(self, before: str = 'filesystems') -> None:
		if 'sd-encrypt' not in self.hooks:
			debug(f'Inserting sd-encrypt hook before {before}')
			self.hooks.insert(self.hooks.index(before), 'sd-encrypt')

	def add_bcachefs(self) -> None:
		if 'bcachefs' not in self.modules:
			debug('Adding bcachefs module to initramfs')
			self.modules.append('bcachefs')
		if 'bcachefs' not in self.hooks and 'block' in self.hooks:
			debug('Inserting bcachefs hook after block')
			self.hooks.insert(self.hooks.index('block') + 1, 'bcachefs')

	def drop_fsck(self) -> None:
		# no fsck tool for ntfs3, the hook would fail on a root it cannot check
		if 'fsck' in self.hooks:
			debug('Removing fsck hook: no fsck tool for ntfs3 root')
			self.hooks.remove('fsck')

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
