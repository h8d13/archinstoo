import platform
import subprocess
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


class GfxPackage(Enum):
	Dkms = 'dkms'
	IntelMediaDriver = 'intel-media-driver'
	LibvaIntelDriver = 'libva-intel-driver'
	LibvaNvidiaDriver = 'libva-nvidia-driver'
	Mesa = 'mesa'  # provides libva-mesa-driver since 24.2.7
	NvidiaOpen = 'nvidia-open'
	NvidiaOpenDkms = 'nvidia-open-dkms'
	VplGpuRt = 'vpl-gpu-rt'  # QSV runtime for Gen12+/Arc; inert on older gens
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
	AllOpenSource = 'all-open-source'
	AmdOpenSource = 'amd-open-source'
	IntelOpenSource = 'intel-open-source'
	NvidiaOpenKernel = 'nvidia-open-kernel'
	NvidiaOpenSource = 'nvidia-open-nouveau'
	MesaOpenSource = 'mesa-open-source'
	VMSoftware = 'vm-software'
	VMVirtio = 'vm-virtio'

	def display_name(self) -> str:
		match self:
			case GfxDriver.AllOpenSource:
				return 'All open-source'
			case GfxDriver.AmdOpenSource:
				return 'AMD / ATI (open-source)'
			case GfxDriver.IntelOpenSource:
				return 'Intel (open-source)'
			case GfxDriver.NvidiaOpenKernel:
				return 'Nvidia (open kernel module for newer GPUs, Turing+)'
			case GfxDriver.NvidiaOpenSource:
				return 'Nvidia (open-source nouveau driver)'
			case GfxDriver.MesaOpenSource:
				return 'Mesa (open-source)'
			case GfxDriver.VMSoftware:
				return 'VM (software rendering)'
			case GfxDriver.VMVirtio:
				return 'VM (virtio-gpu)'

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
		text = 'Installed packages' + ':\n'

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
					GfxPackage.VplGpuRt,
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
					GfxPackage.VplGpuRt,
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


# Module-level so tests can point the sweeps at a synthetic tree
_PCI_BUS = Path('/sys/bus/pci/devices')
_USB_BUS = Path('/sys/bus/usb/devices')
_FIRMWARE_ROOT = Path('/usr/lib/firmware')
_MODULE_ROOT = Path('/usr/lib/modules')

# linux-firmware's OPTIONAL deps only. pacman never pulls them in, so their
# files are absent and firmware_splits can find no owner to name: an ID is the
# last source left. Its hard deps arrive with FULL anyway and stay out of here.
# Vendor-wide, so a ConnectX over-installs a few MB. IDs from pci.ids.
# QCOM has none: SoC blobs sit on the platform bus, no PCI ID to match.
_OPTDEP_PCI: dict[str, str] = {
	'0x1077': 'linux-firmware-qlogic',
	'0x11ab': 'linux-firmware-marvell',
	'0x15b3': 'linux-firmware-mellanox',
	'0x177d': 'linux-firmware-liquidio',  # pci.ids says Cavium
	'0x19ee': 'linux-firmware-nfp',  # pci.ids says Netronome
	'0x1b4b': 'linux-firmware-marvell',
}

# BT radios and wifi dongles hang off USB even when the wifi itself is PCIe
_OPTDEP_USB: dict[str, str] = {
	'1286': 'linux-firmware-marvell',
}

# No bus ID reaches either: CS35L41-class amps enumerate over ACPI/I2C/SPI and
# the catch-all names no vendor
_SPLIT_BASELINE = ('linux-firmware-cirrus', 'linux-firmware-other')


def _run(cmd: list[str]) -> list[str]:
	# pacman -Qo exits 1 over paths it could not match while still printing the
	# owners it did find, so read stdout and ignore the status
	try:
		proc = subprocess.run(cmd, capture_output=True, text=True, check=False)  # noqa: S603 - fixed argv, no user input
	except OSError as err:
		debug(f'{cmd[0]} unavailable: {err}')
		return []

	return [line for line in proc.stdout.splitlines() if line]


def _module_release() -> str:
	# modinfo defaults to the running kernel, whose modules are already gone
	# after an upgrade without a reboot: every lookup would return nothing
	release = platform.release()
	if (_MODULE_ROOT / release).is_dir():
		return release

	installed = sorted(p.name for p in _MODULE_ROOT.glob('*') if (p / 'modules.alias').is_file())
	if len(installed) == 1:
		debug(f'No modules for running kernel {release}, using {installed[0]}')
		return installed[0]

	return release


def _modalias(dev: Path) -> str | None:
	try:
		text = (dev / 'uevent').read_text()
	except OSError:
		return None

	for line in text.splitlines():
		key, _, value = line.partition('=')
		if key == 'MODALIAS':
			return value

	return None


def _bus_optdeps(bus: Path, attr: str, mapping: dict[str, str]) -> set[str]:
	# USB interface nodes (1-1:1.0) carry no vendor-ID attr: skip, do not abort
	if not bus.is_dir():
		return set()

	found: set[str] = set()
	for dev in bus.iterdir():
		try:
			vendor = (dev / attr).read_text().strip().lower()
		except OSError:
			continue

		if pkg := mapping.get(vendor):
			found.add(pkg)

	return found


def _bus_modules(bus: Path) -> set[str]:
	# A driver directory is not a module name: i801_smbus lives in i2c_i801 and
	# modinfo only answers to the latter. Unbound devices have no symlink to
	# follow, so match their modalias against the kernel's own table instead.
	if not bus.is_dir():
		return set()

	modules: set[str] = set()
	for dev in bus.iterdir():
		link = dev / 'driver' / 'module'
		if link.is_symlink():
			modules.add(link.resolve().name)
			continue

		if alias := _modalias(dev):
			modules.update(_run(['modprobe', '-R', alias]))

	return modules


def _firmware_files(declared: list[str], root: Path) -> list[Path]:
	# modinfo reports uncompressed names and shell globs; on disk they are zstd
	# compressed. One file per top-level dir names the package as well as all of
	# them would, which keeps iwlwifi's ~200 flat .ucode entries to one lookup.
	found: dict[str, Path] = {}
	for entry in declared:
		top = entry.split('/')[0] if '/' in entry else ''
		if top in found:
			continue

		if '*' in entry or '?' in entry:
			match = next(iter(sorted(root.glob(entry))), None)
		else:
			match = next((p for p in (root / entry, root / f'{entry}.zst') if p.is_file()), None)

		if match:
			found[top] = match

	return list(found.values())


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
			with (self.efi_path / 'fw_platform_size').open() as fw_ps:
				return int(fw_ps.read().strip())
		except OSError:
			return None

	@cached_property
	def has_battery(self) -> bool:
		for type_path in Path('/sys/class/power_supply/').glob('*/type'):
			try:
				with type_path.open() as f:
					if f.read().strip() == 'Battery':
						return True
			except OSError:
				continue

		return False

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
	def loaded_modules(self) -> list[str]:
		# Returns loaded kernel modules
		modules_path = Path('/proc/modules')
		modules: list[str] = []

		with modules_path.open() as file:
			for line in file:
				module = line.split(maxsplit=1)[0]
				modules.append(module)

		return modules

	@cached_property
	def graphics_devices(self) -> dict[str, str]:
		# Returns detected graphics devices
		cards: dict[str, str] = {}
		for line in SysCommand('lspci'):
			if b' VGA ' in line or b' 3D ' in line:
				_, identifier = line.split(b': ', 1)
				cards[identifier.strip().decode('UTF-8')] = str(line)
		return cards

	@cached_property
	def is_vm(self) -> bool:
		# Forks systemd-detect-virt, and gates the firmware scan, microcode and
		# the gfx driver list. A host does not become a VM mid-run
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

		vendor = Path('/sys/class/dmi/id/sys_vendor')
		if vendor.exists():
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
			text = vendor.read_text().strip().lower()
			return any(v in text for v in known)

		return False

	@cached_property
	def firmware_optdeps(self) -> list[str]:
		# Sysfs only, no subprocess, so the FULL install path can afford it
		detected = _bus_optdeps(_PCI_BUS, 'vendor', _OPTDEP_PCI)
		detected |= _bus_optdeps(_USB_BUS, 'idVendor', _OPTDEP_USB)

		return sorted(detected)

	@cached_property
	def firmware_splits(self) -> list[str]:
		# device -> module -> firmware file -> owning package. Under-detects:
		# rtw88/rtw89/btusb build their names at runtime and declare none, and a
		# proprietary driver's blobs are unowned. Only VENDOR trimming reads
		# this, so a miss shrinks a trim, never drops a blob FULL would install.
		release = _module_release()
		modules = _bus_modules(_PCI_BUS) | _bus_modules(_USB_BUS)

		files: list[Path] = []
		for module in sorted(modules):
			declared = _run(['modinfo', '-k', release, '-F', 'firmware', module])
			files += _firmware_files(declared, _FIRMWARE_ROOT)

		detected = set(_SPLIT_BASELINE)
		if files:
			owners = _run(['pacman', '-Qoq', *(str(f) for f in files)])
			# sof-firmware and the nvidia driver tree also live under there
			detected |= {pkg for pkg in owners if pkg.startswith('linux-firmware-')}

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
	def firmware_optdep_packages() -> list[str]:
		# Not skipped on VMs: passthrough hardware is real hardware
		return _sys_info.firmware_optdeps

	@staticmethod
	def firmware_split_packages() -> list[str]:
		# virtio ships no blobs, and the scan costs a modinfo per bound driver
		if SysInfo.is_vm():
			return []
		return _sys_info.firmware_splits

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
			with Path('/sys/devices/virtual/dmi/id/sys_vendor').open() as vendor:
				return vendor.read().strip()
		except FileNotFoundError:
			return None

	@staticmethod
	def product_name() -> str | None:
		try:
			with Path('/sys/devices/virtual/dmi/id/product_name').open() as product:
				return product.read().strip()
		except FileNotFoundError:
			return None

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

		return any(loaded_module in modules for loaded_module in _sys_info.loaded_modules)
