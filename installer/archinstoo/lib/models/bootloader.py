from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Self

from archinstoo.lib.output import warn

# where Fedora's shim and signed grub RPMs put themselves: the ESP has to be
# mounted here for GRUB on UEFI
GRUB_ESP = Path('/boot/efi')


class Bootloader(Enum):
	Systemd = 'systemd-boot'
	Grub = 'grub'

	def display_name(self) -> str:
		match self:
			case Bootloader.Systemd:
				return 'Systemd-boot'
			case Bootloader.Grub:
				return 'Grub'

	def packages(self, uefi: bool = True, uki: bool = False) -> list[str]:
		# what the bootloader step straps. The default is the UEFI set, the
		# upper bound an estimate wants
		match self:
			case Bootloader.Systemd:
				# systemd-boot-unsigned carries the stub ukify wraps a UKI in
				return ['systemd-boot-unsigned', *(['systemd-ukify'] if uki else [])]
			case Bootloader.Grub:
				if uefi:
					# signed shim + grub, prebuilt: Secure Boot works as shipped
					return ['grub2-efi-x64', 'shim-x64', 'grub2-tools', 'efibootmgr']
				return ['grub2-pc', 'grub2-tools']

	def has_removable_support(self) -> bool:
		# shim-x64 ships EFI/BOOT/BOOTX64.EFI; bootctl always writes it
		return self == Bootloader.Grub

	def has_bios_support(self) -> bool:
		return self == Bootloader.Grub

	def has_uki_support(self) -> bool:
		# GRUB's BLS entries name a kernel and an initrd, not a UKI
		return self == Bootloader.Systemd

	def json(self) -> str:
		return self.value

	@classmethod
	def from_arg(cls, bootloader: str) -> Self:
		bootloader_options = [e.value for e in cls]

		if bootloader not in bootloader_options:
			values = ', '.join(bootloader_options)
			warn(f'Invalid bootloader value "{bootloader}". Allowed values: {values}')
			raise SystemExit(1)

		return cls(bootloader)


@dataclass
class BootloaderConfiguration:
	bootloader: Bootloader | None
	uki: bool = False
	removable: bool = True
	quiet: bool = False
	# kernel 'console=' value (e.g. 'ttyS0,115200'); None = no serial console
	serial_console: str | None = None

	def json(self) -> dict[str, Any]:
		return {
			'bootloader': self.bootloader.json() if self.bootloader else None,
			'uki': self.uki,
			'removable': self.removable,
			'quiet': self.quiet,
			'serial_console': self.serial_console,
		}

	@classmethod
	def parse_arg(cls, config: dict[str, Any]) -> Self:
		raw = config.get('bootloader')
		bootloader = Bootloader.from_arg(raw) if raw else None
		uki = config.get('uki', False)
		removable = config.get('removable', True)
		quiet = config.get('quiet', False)
		serial_console = config.get('serial_console') or None
		return cls(
			bootloader=bootloader,
			uki=uki,
			removable=removable,
			quiet=quiet,
			serial_console=serial_console,
		)

	@classmethod
	def get_default(cls, uefi: bool, skip_boot: bool = False) -> Self:
		# Fedora's own default: shim-signed GRUB over BLS entries
		bootloader = None if skip_boot else Bootloader.Grub
		removable = uefi and bootloader is not None and bootloader.has_removable_support()
		uki = uefi and bootloader is not None and bootloader.has_uki_support()
		return cls(bootloader=bootloader, uki=uki, removable=removable)

	def preview(self, uefi: bool) -> str:
		text = f'Bootloader: {self.bootloader.display_name() if self.bootloader else "None"}'
		text += '\n'
		if self.bootloader is None:
			return text
		if uefi and self.bootloader.has_uki_support():
			uki_string = 'Enabled' if self.uki else 'Disabled'
			text += f'UKI: {uki_string}'
			text += '\n'
		if uefi and self.bootloader.has_removable_support():
			removable_string = 'Enabled' if self.removable else 'Disabled'
			text += f'Removable: {removable_string}'
			text += '\n'
		text += f'Quiet boot: {"Enabled" if self.quiet else "Disabled"}\n'
		text += f'Serial console: {self.serial_console or "Disabled"}\n'
		return text
