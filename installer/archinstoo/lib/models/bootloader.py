from dataclasses import dataclass
from enum import Enum
from typing import Any, Self

from archinstoo.lib.output import warn

# writes the EFI boot entry, for every bootloader that does not manage its own
EFIBOOTMGR = 'efibootmgr'


class Bootloader(Enum):
	Systemd = 'systemd-boot'
	Grub = 'grub'
	Efistub = 'efistub'
	Limine = 'limine'
	Refind = 'refind'

	def display_name(self) -> str:
		match self:
			case Bootloader.Systemd:
				return 'Systemd-boot'
			case Bootloader.Grub:
				return 'Grub'
			case Bootloader.Efistub:
				return 'Efistub'
			case Bootloader.Limine:
				return 'Limine'
			case Bootloader.Refind:
				return 'Refind'

	def packages(self, uefi: bool = True) -> list[str]:
		# what _add_<name>_bootloader() straps. the default is the UEFI set,
		# the upper bound an estimate wants: a BIOS install has no EFI entry to
		# write, and refind-install writes its own
		match self:
			case Bootloader.Grub | Bootloader.Limine:
				return [self.value, *([EFIBOOTMGR] if uefi else [])]
			case Bootloader.Refind:
				return [self.value]
			case _:
				# systemd-boot ships with systemd, efistub is a kernel feature
				return [EFIBOOTMGR]

	def has_removable_support(self) -> bool:
		match self:
			case Bootloader.Grub | Bootloader.Limine:
				return True
			case _:
				return False

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
	# embeds the Arch splash bmp into the UKI; only meaningful with uki=True
	splash: bool = False
	# kernel 'console=' value (e.g. 'ttyS0,115200'); None = no serial console
	serial_console: str | None = None

	def json(self) -> dict[str, Any]:
		return {
			'bootloader': self.bootloader.json() if self.bootloader else None,
			'uki': self.uki,
			'removable': self.removable,
			'quiet': self.quiet,
			'splash': self.splash,
			'serial_console': self.serial_console,
		}

	@classmethod
	def parse_arg(cls, config: dict[str, Any]) -> Self:
		raw = config.get('bootloader')
		bootloader = Bootloader.from_arg(raw) if raw else None
		uki = config.get('uki', False)
		removable = config.get('removable', True)
		quiet = config.get('quiet', False)
		splash = config.get('splash', False)
		serial_console = config.get('serial_console') or None
		return cls(
			bootloader=bootloader,
			uki=uki,
			removable=removable,
			quiet=quiet,
			splash=splash,
			serial_console=serial_console,
		)

	@classmethod
	def get_default(cls, uefi: bool, skip_boot: bool = False) -> Self:
		bootloader = None if skip_boot else Bootloader.Grub
		removable = uefi and bootloader is not None and bootloader.has_removable_support()
		uki = uefi and bootloader is not None
		return cls(bootloader=bootloader, uki=uki, removable=removable)

	def preview(self, uefi: bool) -> str:
		text = f'{"Bootloader"}: {self.bootloader.display_name() if self.bootloader else "None"}'
		text += '\n'
		if self.bootloader is None:
			return text
		if uefi:
			uki_string = 'Enabled' if self.uki else 'Disabled'
			text += f'UKI: {uki_string}'
			text += '\n'
			if self.uki:
				splash_string = 'Enabled' if self.splash else 'Disabled'
				text += f'Boot splash: {splash_string}'
				text += '\n'
		if uefi and self.bootloader.has_removable_support():
			removable_string = 'Enabled' if self.removable else 'Disabled'
			text += f'{"Removable"}: {removable_string}'
			text += '\n'
		text += '{}: {}\n'.format('Quiet boot', 'Enabled' if self.quiet else 'Disabled')
		text += '{}: {}\n'.format('Serial console', self.serial_console or 'Disabled')
		return text
