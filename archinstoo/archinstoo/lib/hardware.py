import os
import platform
from enum import Enum
from functools import cached_property
from pathlib import Path
from typing import Self, cast

from .exceptions import SysCallError
from .general import SysCommand
from .output import debug
from .translationhandler import tr


class CpuVendor(Enum):
	AuthenticAMD = 'amd'
	GenuineIntel = 'intel'
	_Unknown = 'unknown'

	@classmethod
	def get_vendor(cls, name: str) -> Self:
		if vendor := getattr(cls, name, None):
			return cast(Self, vendor)
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


class GfxPackage(Enum):
	Dkms = 'dkms'
	IntelMediaDriver = 'intel-media-driver'
	LibvaIntelDriver = 'libva-intel-driver'
	LibvaNvidiaDriver = 'libva-nvidia-driver'
	Mesa = 'mesa'  # provides libva-mesa-driver since 24.2.7
	NvidiaOpen = 'nvidia-open'
	NvidiaOpenDkms = 'nvidia-open-dkms'
	VulkanIntel = 'vulkan-intel'
	VulkanRadeon = 'vulkan-radeon'
	VulkanNouveau = 'vulkan-nouveau'
	VulkanSwrast = 'vulkan-swrast'
	VulkanVirtio = 'vulkan-virtio'
	Xf86VideoAmdgpu = 'xf86-video-amdgpu'
	Xf86VideoAti = 'xf86-video-ati'
	Xf86VideoNouveau = 'xf86-video-nouveau'
	XorgServer = 'xorg-server'
	XorgXinit = 'xorg-xinit'


class GfxDriver(Enum):
	AllOpenSource = 'All open-source'
	AmdOpenSource = 'AMD / ATI (open-source)'
	IntelOpenSource = 'Intel (open-source)'
	NvidiaOpenKernel = 'Nvidia (open kernel module for newer GPUs, Turing+)'
	NvidiaOpenSource = 'Nvidia (open-source nouveau driver)'
	MesaOpenSource = 'Mesa (open-source)'
	VMSoftware = 'VM (software rendering)'
	VMVirtio = 'VM (virtio-gpu)'

	def has_dkms_variant(self) -> bool:
		match self:
			case GfxDriver.NvidiaOpenKernel:
				return True
			case _:
				return False

	def use_dkms(self, kernels: list[str] | None) -> bool:
		if not self.has_dkms_variant():
			return False
		return kernels is not None and any('-' in k for k in kernels)

	def packages_text(self, kernels: list[str] | None = None) -> str:
		pkg_names = [p.value for p in self.gfx_packages(kernels)]
		text = tr('Installed packages') + ':\n'

		for p in sorted(pkg_names):
			text += f'\t- {p}\n'

		return text

	def gfx_packages(self, kernels: list[str] | None = None) -> list[GfxPackage]:
		# GPU-vendor packages only. xorg-server/xorg-xinit are a display-server concern
		# and added by the caller (profiles_handler.install_gfx_driver) when X11 is in use.
		packages: list[GfxPackage] = []

		match self:
			case GfxDriver.AllOpenSource:
				packages += [
					GfxPackage.Mesa,
					GfxPackage.Xf86VideoAmdgpu,
					GfxPackage.Xf86VideoAti,
					GfxPackage.Xf86VideoNouveau,
					GfxPackage.LibvaIntelDriver,
					GfxPackage.IntelMediaDriver,
					GfxPackage.VulkanRadeon,
					GfxPackage.VulkanIntel,
					GfxPackage.VulkanNouveau,
				]
			case GfxDriver.AmdOpenSource:
				packages += [
					GfxPackage.Mesa,
					GfxPackage.Xf86VideoAmdgpu,
					GfxPackage.Xf86VideoAti,
					GfxPackage.VulkanRadeon,
				]
			case GfxDriver.IntelOpenSource:
				packages += [
					GfxPackage.Mesa,
					GfxPackage.LibvaIntelDriver,
					GfxPackage.IntelMediaDriver,
					GfxPackage.VulkanIntel,
				]
			case GfxDriver.NvidiaOpenKernel:
				nvidia_pkg = GfxPackage.NvidiaOpenDkms if self.use_dkms(kernels) else GfxPackage.NvidiaOpen
				packages += [
					nvidia_pkg,
					GfxPackage.LibvaNvidiaDriver,
				]
				if self.use_dkms(kernels):
					packages.append(GfxPackage.Dkms)
			case GfxDriver.NvidiaOpenSource:
				packages += [
					GfxPackage.Mesa,
					GfxPackage.Xf86VideoNouveau,
					GfxPackage.VulkanNouveau,
				]
			case GfxDriver.MesaOpenSource:
				packages += [
					GfxPackage.Mesa,
				]
				# Add driver based on detection
				if SysInfo.has_intel_graphics():
					packages.append(GfxPackage.VulkanIntel)
				elif SysInfo.has_amd_graphics():
					packages.append(GfxPackage.VulkanRadeon)
			case GfxDriver.VMSoftware:
				packages += [
					GfxPackage.Mesa,
					GfxPackage.VulkanSwrast,
				]
			case GfxDriver.VMVirtio:
				packages += [
					GfxPackage.Mesa,
					GfxPackage.VulkanVirtio,
				]

		return packages


class _SysInfo:
	efi_path = '/sys/firmware/efi'

	def __init__(self) -> None:
		pass

	@cached_property
	def has_uefi(self) -> bool:
		return os.path.isdir(self.efi_path)

	@cached_property
	def efi_bitness(self) -> int | None:
		try:
			with open(f'{self.efi_path}/fw_platform_size') as fw_ps:
				return int(fw_ps.read().strip())
		except FileNotFoundError, OSError:
			return None

	@cached_property
	def has_battery(self) -> bool:
		for type_path in Path('/sys/class/power_supply/').glob('*/type'):
			try:
				with open(type_path) as f:
					if f.read().strip() == 'Battery':
						return True
			except OSError:
				continue

		return False

	@cached_property
	def cpu_info(self) -> dict[str, str]:
		"""
		Returns system cpu information
		"""
		cpu_info_path = Path('/proc/cpuinfo')
		cpu: dict[str, str] = {}

		with cpu_info_path.open() as file:
			for line in file:
				if line := line.strip():
					key, value = line.split(':', maxsplit=1)
					cpu[key.strip()] = value.strip()

		return cpu

	@cached_property
	def mem_info(self) -> dict[str, int]:
		"""
		Returns system memory information
		"""
		mem_info_path = Path('/proc/meminfo')
		mem_info: dict[str, int] = {}

		with mem_info_path.open() as file:
			for line in file:
				key, value = line.strip().split(':')
				num = value.split()[0]
				mem_info[key] = int(num)

		return mem_info

	def mem_info_by_key(self, key: str) -> int:
		return self.mem_info[key]

	@cached_property
	def loaded_modules(self) -> list[str]:
		"""
		Returns loaded kernel modules
		"""
		modules_path = Path('/proc/modules')
		modules: list[str] = []

		with modules_path.open() as file:
			for line in file:
				module = line.split(maxsplit=1)[0]
				modules.append(module)

		return modules

	@cached_property
	def graphics_devices(self) -> dict[str, str]:
		"""
		Returns detected graphics devices (cached)
		"""
		cards: dict[str, str] = {}
		for line in SysCommand('lspci'):
			if b' VGA ' in line or b' 3D ' in line:
				_, identifier = line.split(b': ', 1)
				cards[identifier.strip().decode('UTF-8')] = str(line)
		return cards

	@cached_property
	def firmware_vendors(self) -> list[str]:
		"""
		Returns FirmwareVendor enum *names* matching detected PCI vendor IDs.
		Returns names rather than enum instances so this module stays free of any
		models/* import (avoids contributing to a hardware <-> models cycle).
		Limited to high-yield consumer vendors; niche vendors stay manual.
		"""
		# Manual-only FirmwareVendor members (not auto-detected, ticked by the user)
		#   LIQUIDIO  	Cavium LiquidIO server adapters
		#   MARVELL   	Marvell devices
		#   MELLANOX  	Mellanox Spectrum switches
		#   NFP       	Netronome Flow Processors
		#   QLOGIC    	QLogic devices
		mapping: dict[str, tuple[str, ...]] = {
			'0x10de': ('NVIDIA',),
			'0x8086': ('INTEL',),
			'0x10ec': ('REALTEK',),
			'0x14e4': ('BROADCOM',),
			'0x168c': ('ATHEROS',),
			'0x0cf3': ('ATHEROS',),
			'0x14c3': ('MEDIATEK',),
			'0x17cb': ('QCOM',),
		}

		pci_devs = Path('/sys/bus/pci/devices')
		if not pci_devs.is_dir():
			return []

		detected: set[str] = set()
		for dev in pci_devs.iterdir():
			try:
				vendor = (dev / 'vendor').read_text().strip().lower()
			except OSError:
				continue

			# AMD (0x1002) shares a vendor ID across GCN generations: amdgpu drives newer
			# cards, radeon drives older. The kernel binds the right one on the live ISO,
			# so the bound driver name tells us which firmware subpackage to suggest.
			if vendor == '0x1002':
				try:
					driver = (dev / 'driver').readlink().name
				except OSError:
					driver = ''
				if driver == 'amdgpu':
					detected.add('AMDGPU')
				elif driver == 'radeon':
					detected.add('RADEON')
				else:
					# No AMD driver bound fall back to newer
					detected.add('AMDGPU')
				continue

			if mapped := mapping.get(vendor):
				detected.update(mapped)

		return sorted(detected)


_sys_info = _SysInfo()


class SysInfo:
	@staticmethod
	def has_uefi() -> bool:
		return _sys_info.has_uefi

	@staticmethod
	def has_tpm2() -> bool:
		# Detects a TPM 2.0 chip via /sys/class/tpm/<dev>/tpm_version_major == 2.
		# Filters out TPM 1.2 chips, which systemd-cryptenroll cannot bind to.
		tpm_dir = Path('/sys/class/tpm')
		if not tpm_dir.is_dir():
			return False
		for dev in tpm_dir.iterdir():
			ver_file = dev / 'tpm_version_major'
			try:
				if ver_file.read_text().strip() == '2':
					return True
			except OSError:
				continue
		return False

	@staticmethod
	def _bitness() -> int | None:
		return _sys_info.efi_bitness

	@staticmethod
	def arch() -> str:
		return platform.machine()

	@staticmethod
	def has_battery() -> bool:
		return _sys_info.has_battery

	@staticmethod
	def _graphics_devices() -> dict[str, str]:
		return _sys_info.graphics_devices

	@staticmethod
	def has_nvidia_graphics() -> bool:
		return any('nvidia' in x.lower() for x in _sys_info.graphics_devices)

	@staticmethod
	def has_amd_graphics() -> bool:
		return any('amd' in x.lower() for x in _sys_info.graphics_devices)

	@staticmethod
	def has_intel_graphics() -> bool:
		return any('intel' in x.lower() for x in _sys_info.graphics_devices)

	@staticmethod
	def firmware_vendor_names() -> list[str]:
		# Skip the PCI scan on VMs. Returns FirmwareVendor enum names; caller resolves
		# via FirmwareVendor[name] to keep this module free of any models import.
		if SysInfo.is_vm():
			return []
		return _sys_info.firmware_vendors

	@staticmethod
	def cpu_vendor() -> CpuVendor | None:
		if vendor := _sys_info.cpu_info.get('vendor_id'):
			return CpuVendor.get_vendor(vendor)
		return None

	@staticmethod
	def cpu_model() -> str | None:
		return _sys_info.cpu_info.get('model name', None)

	@staticmethod
	def sys_vendor() -> str | None:
		try:
			with open('/sys/devices/virtual/dmi/id/sys_vendor') as vendor:
				return vendor.read().strip()
		except FileNotFoundError:
			return None

	@staticmethod
	def product_name() -> str | None:
		try:
			with open('/sys/devices/virtual/dmi/id/product_name') as product:
				return product.read().strip()
		except FileNotFoundError:
			return None

	@staticmethod
	def mem_total() -> int:
		return _sys_info.mem_info_by_key('MemTotal')

	@staticmethod
	def is_vm() -> bool:
		try:
			result = SysCommand('systemd-detect-virt')
			return b'none' not in b''.join(result).lower()
		except SysCallError:
			pass

		return False

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

		return any(loaded_module in modules for loaded_module in _sys_info.loaded_modules)
