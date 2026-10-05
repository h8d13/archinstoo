import platform
from enum import Enum
from functools import cached_property
from pathlib import Path

from .exceptions import RequirementError, SysCallError
from .general import SysCommand
from .output import debug


class CpuVendor(Enum):
	AuthenticAMD = 'amd'
	GenuineIntel = 'intel'
	_Unknown = 'unknown'

	@classmethod
	def get_vendor(cls, name: str) -> CpuVendor:
		if name in cls.__members__:
			return cls[name]
		debug(f"Unknown CPU vendor '{name}' detected.")
		return cls._Unknown

	def _has_microcode(self) -> bool:
		match self:
			case CpuVendor.AuthenticAMD | CpuVendor.GenuineIntel:
				return True
			case _:
				return False

	def get_ucode(self) -> Path | None:
		if self._has_microcode():
			return Path(self.value + '-ucode.img')
		return None


_DMI_ID = Path('/sys/class/dmi/id')
_PROC_MODULES = Path('/proc/modules')


def _read_dmi(attr: str) -> str | None:
	try:
		return (_DMI_ID / attr).read_text().strip()
	except OSError:
		return None


class _SysInfo:
	efi_path = Path('/sys/firmware/efi')

	def __init__(self) -> None:
		pass

	@cached_property
	def has_uefi(self) -> bool:
		return self.efi_path.is_dir()

	@cached_property
	def efi_bitness(self) -> int | None:
		try:
			return int((self.efi_path / 'fw_platform_size').read_text().strip())
		except OSError:
			return None

	@cached_property
	def has_battery(self) -> bool:
		for type_path in Path('/sys/class/power_supply/').glob('*/type'):
			try:
				if type_path.read_text().strip() == 'Battery':
					return True
			except OSError:
				continue

		return False

	@cached_property
	def has_thunderbolt(self) -> bool:
		# one domainN per host controller bound by the thunderbolt driver
		# (USB4 hosts register on the same bus); disabled in firmware = absent
		return any(Path('/sys/bus/thunderbolt/devices').glob('domain*'))

	@cached_property
	def cpu_info(self) -> dict[str, str]:
		# Returns system cpu information
		cpu_info_path = Path('/proc/cpuinfo')
		cpu: dict[str, str] = {}

		with cpu_info_path.open() as file:
			for line in file:
				if line := line.strip():
					key, value = line.split(':', maxsplit=1)
					cpu[key.strip()] = value.strip()

		return cpu

	@cached_property
	def mem_total(self) -> int:
		# kB. Single key, so no dict of the whole file: MemFree/MemAvailable
		# are live values and caching them would be wrong anyway.
		with Path('/proc/meminfo').open() as file:
			for line in file:
				key, _, remainder = line.partition(':')
				if key == 'MemTotal':
					return int(remainder.split()[0])

		raise RequirementError('MemTotal missing from /proc/meminfo')

	@cached_property
	def sys_vendor(self) -> str | None:
		return _read_dmi('sys_vendor')

	@cached_property
	def product_name(self) -> str | None:
		return _read_dmi('product_name')

	@cached_property
	def loaded_modules(self) -> set[str]:
		with _PROC_MODULES.open() as file:
			return {line.split(maxsplit=1)[0] for line in file if line.strip()}

	@cached_property
	def is_vm(self) -> bool:
		# Forks systemd-detect-virt, and gates microcode and the firmware
		# default. A host does not become a VM mid-run
		try:
			result = SysCommand('systemd-detect-virt')
			return b'none' not in b''.join(result).lower()
		except SysCallError:
			# present but reported an error, treat as bare metal
			return False
		except RequirementError:
			# non-systemd host (e.g. alpine): binary absent, fall back to DMI
			pass

		# xen exposes its type here, and the DMI vendor names the hypervisor for
		# kvm/qemu/vmware/virtualbox/hyper-v on anything with a sysfs
		if Path('/sys/hypervisor/type').exists():
			return True

		if vendor := self.sys_vendor:
			known = (
				'qemu',
				'kvm',
				'vmware',
				'virtualbox',
				'innotek',
				'microsoft corporation',
				'xen',
				'bochs',
				'parallels',
				'bhyve',
			)
			return any(v in vendor.lower() for v in known)

		return False


_sys_info = _SysInfo()


class SysInfo:
	@staticmethod
	def has_uefi() -> bool:
		return _sys_info.has_uefi

	@staticmethod
	def bitness() -> int | None:
		return _sys_info.efi_bitness

	@staticmethod
	def arch() -> str:
		return platform.machine()

	@staticmethod
	def has_battery() -> bool:
		return _sys_info.has_battery

	@staticmethod
	def has_thunderbolt() -> bool:
		return _sys_info.has_thunderbolt

	@staticmethod
	def cpu_vendor() -> CpuVendor | None:
		if vendor := _sys_info.cpu_info.get('vendor_id'):
			return CpuVendor.get_vendor(vendor)
		return None

	@staticmethod
	def ucode() -> Path | None:
		# a VM gets its microcode from the hypervisor, the image would only
		# be dead weight in /boot
		if not SysInfo.is_vm() and (vendor := SysInfo.cpu_vendor()):
			return vendor.get_ucode()
		return None

	@staticmethod
	def cpu_model() -> str | None:
		return _sys_info.cpu_info.get('model name', None)

	@staticmethod
	def sys_vendor() -> str | None:
		return _sys_info.sys_vendor

	@staticmethod
	def product_name() -> str | None:
		return _sys_info.product_name

	@staticmethod
	def mem_total() -> int:
		return _sys_info.mem_total

	@staticmethod
	def is_vm() -> bool:
		return _sys_info.is_vm

	@staticmethod
	def requires_sof_fw() -> bool:
		return 'snd_sof' in _sys_info.loaded_modules

	@staticmethod
	def requires_alsa_fw() -> bool:
		modules = (
			'snd_asihpi',
			'snd_cs46xx',
			'snd_darla20',
			'snd_darla24',
			'snd_echo3g',
			'snd_emu10k1',
			'snd_gina20',
			'snd_gina24',
			'snd_hda_codec_ca0132',
			'snd_hdsp',
			'snd_indigo',
			'snd_indigodj',
			'snd_indigodjx',
			'snd_indigoio',
			'snd_indigoiox',
			'snd_layla20',
			'snd_layla24',
			'snd_mia',
			'snd_mixart',
			'snd_mona',
			'snd_pcxhr',
			'snd_vx_lib',
		)

		return not _sys_info.loaded_modules.isdisjoint(modules)
