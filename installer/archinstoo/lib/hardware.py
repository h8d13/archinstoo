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
	VplGpuRt = 'vpl-gpu-rt'
	LibVpl = 'libvpl'
	VulkanIntel = 'vulkan-intel'
	VulkanMesaLayers = 'vulkan-mesa-layers'
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
	Custom = 'custom'

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
			case GfxDriver.Custom:
				return 'Custom (pick packages)'

	def has_dkms_variant(self) -> bool:
		match self:
			case GfxDriver.NvidiaOpenKernel:
				return True
			case _:
				return False

	def packages_text(self, kernels: list[str] | None = None) -> str:
		if self is GfxDriver.Custom:
			return 'Packages are picked one by one in the next menu (hybrid GPUs, unlisted mixes)\n'

		pkg_names = [p.value for p in self.gfx_packages(kernels)]
		text = 'Installed packages' + ':\n'

		for p in sorted(pkg_names):
			text += f'\t- {p}\n'

		return text

	def gfx_packages(self, kernels: list[str] | None = None) -> list[GfxPackage]:
		# GPU-vendor packages only. xorg-server/xorg-xinit are a display-server concern
		# and added by the caller (profiles_handler.install_gfx_driver) when X11 is in use.
		packages = dkms_packages(GFX_PACKAGES[self], kernels)

		# the generic driver adds the vulkan driver of every GPU present
		if self is GfxDriver.MesaOpenSource:
			for vendor in gpu_vendors(SysInfo.gpu_ids()):
				packages += MESA_HOST_EXTRA[vendor]

		return packages


def needs_dkms_build(kernels: list[str] | None) -> bool:
	# anything but plain `linux` has no prebuilt nvidia-open module
	return kernels is not None and any('-' in k for k in kernels)


def dkms_packages(packages: list[GfxPackage], kernels: list[str] | None) -> list[GfxPackage]:
	# nvidia-open is the only out-of-tree driver: a non-standard kernel swaps
	# it for the dkms build and pulls dkms itself. Everything else is in-tree
	if GfxPackage.NvidiaOpen not in packages or not needs_dkms_build(kernels):
		return list(packages)
	swapped: list[GfxPackage] = [GfxPackage.NvidiaOpenDkms if p is GfxPackage.NvidiaOpen else p for p in packages]
	return [*swapped, GfxPackage.Dkms]


# what the custom driver lets a user tick. dkms and its nvidia variant are
# derived from the kernel list, xorg from the profile's display server
GFX_CUSTOM_CHOICES: list[GfxPackage] = [
	p for p in GfxPackage if p not in (GfxPackage.Dkms, GfxPackage.NvidiaOpenDkms, GfxPackage.XorgServer, GfxPackage.XorgXinit)
]

_PCI_VENDOR_AMD = 0x1002  # ATI's ID, every AMD GPU still carries it
_PCI_VENDOR_INTEL = 0x8086
_PCI_VENDOR_NVIDIA = 0x10DE
_GFX_BY_VENDOR: dict[int, GfxDriver] = {_PCI_VENDOR_AMD: GfxDriver.AmdOpenSource, _PCI_VENDOR_INTEL: GfxDriver.IntelOpenSource}
_GPU_VENDORS: dict[int, str] = {_PCI_VENDOR_AMD: 'amd', _PCI_VENDOR_INTEL: 'intel', _PCI_VENDOR_NVIDIA: 'nvidia'}
# nvidia-open needs the GSP, so Turing on: TU102 opens at 0x1e02 and every
# later generation numbers higher. Volta (GV100, 0x1d81) stays below
_NVIDIA_TURING_FIRST = 0x1E00


def detected_gfx_drivers(gpus: set[tuple[int, int]]) -> list[GfxDriver]:
	# one preset per GPU; a hybrid yields two, which only the custom driver
	# can hold at once
	drivers: list[GfxDriver] = []
	for vendor, device in sorted(gpus):
		driver = _GFX_BY_VENDOR.get(vendor)
		if vendor == _PCI_VENDOR_NVIDIA:
			driver = GfxDriver.NvidiaOpenKernel if device >= _NVIDIA_TURING_FIRST else GfxDriver.NvidiaOpenSource
		if driver and driver not in drivers:
			drivers.append(driver)
	return drivers


def gpu_vendors(gpus: set[tuple[int, int]]) -> list[str]:
	# known vendors only: a server's BMC (ASPEED) is display class too
	return sorted({_GPU_VENDORS[vendor] for vendor, _ in gpus if vendor in _GPU_VENDORS})


def detected_gfx_packages(gpus: set[tuple[int, int]]) -> list[GfxPackage]:
	# the union of the matching presets, first occurrence wins the order
	packages: list[GfxPackage] = []
	for driver in detected_gfx_drivers(gpus):
		packages += [p for p in GFX_PACKAGES[driver] if p not in packages]
	return packages


# the static half of every driver, before the DKMS and host-GPU conditionals
GFX_PACKAGES: dict[GfxDriver, list[GfxPackage]] = {
	GfxDriver.AllOpenSource: [
		GfxPackage.Mesa,
		GfxPackage.Xf86VideoAmdgpu,
		GfxPackage.Xf86VideoAti,
		GfxPackage.Xf86VideoNouveau,
		GfxPackage.LibvaIntelDriver,
		GfxPackage.IntelMediaDriver,
		GfxPackage.VplGpuRt,
		GfxPackage.LibVpl,
		GfxPackage.VulkanRadeon,
		GfxPackage.VulkanIntel,
		GfxPackage.VulkanNouveau,
	],
	GfxDriver.AmdOpenSource: [
		GfxPackage.Mesa,
		GfxPackage.Xf86VideoAmdgpu,
		GfxPackage.Xf86VideoAti,
		GfxPackage.VulkanRadeon,
	],
	GfxDriver.IntelOpenSource: [
		GfxPackage.Mesa,
		GfxPackage.LibvaIntelDriver,
		GfxPackage.IntelMediaDriver,
		GfxPackage.VplGpuRt,
		GfxPackage.LibVpl,
		GfxPackage.VulkanIntel,
	],
	GfxDriver.NvidiaOpenKernel: [
		GfxPackage.NvidiaOpen,
		GfxPackage.LibvaNvidiaDriver,
	],
	GfxDriver.NvidiaOpenSource: [
		GfxPackage.Mesa,
		GfxPackage.Xf86VideoNouveau,
		GfxPackage.VulkanNouveau,
	],
	GfxDriver.MesaOpenSource: [
		GfxPackage.Mesa,
	],
	GfxDriver.VMSoftware: [
		GfxPackage.Mesa,
		GfxPackage.VulkanSwrast,
	],
	GfxDriver.Custom: [],
	GfxDriver.VMVirtio: [
		GfxPackage.Mesa,
		GfxPackage.VulkanVirtio,
	],
}

# what MesaOpenSource adds per GPU vendor present
MESA_HOST_EXTRA: dict[str, list[GfxPackage]] = {
	'amd': [GfxPackage.VulkanRadeon],
	'intel': [GfxPackage.VulkanIntel],
	'nvidia': [GfxPackage.VulkanNouveau],
}

# the X11 half of a graphical install, added off DisplayServer rather than
# off the driver (profiles_handler.install_gfx_driver)
XORG_EXTRA: list[GfxPackage] = [GfxPackage.XorgServer, GfxPackage.XorgXinit]

# Module-level so tests can point the sweeps at a synthetic tree
_SYS_BUS = Path('/sys/bus')
_PCI_BUS = _SYS_BUS / 'pci/devices'
# amps enumerate on acpi and bind on i2c/spi, codecs on hdaudio, SoC blocks on platform
_MODULE_BUSES = ('pci', 'usb', 'acpi', 'hdaudio', 'i2c', 'platform', 'sdio', 'soundwire', 'spi')
_MODULE_ROOT = Path('/usr/lib/modules')
_PROC_FILESYSTEMS = Path('/proc/filesystems')
_DMI_ID = Path('/sys/class/dmi/id')
# SMBIOS portable chassis: chwd's laptop set plus sub notebook and detachable
_PORTABLE_CHASSIS = frozenset({'8', '9', '10', '11', '14', '31', '32'})


def _run_splitlines(cmd: list[str]) -> list[str]:
	# a nonzero exit from modinfo/modprobe -R only means no answer
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


def _read_dmi(attr: str) -> str | None:
	try:
		return (_DMI_ID / attr).read_text().strip()
	except OSError:
		return None


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


def _bus_modules(bus: Path, release: str) -> set[str]:
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
			modules.update(_run_splitlines(['modprobe', '-S', release, '-R', alias]))

	return modules


def _module_depends(release: str, module: str) -> set[str]:
	# Bus wrappers declare no firmware: snd_hda_scodec_cs35l41_i2c binds the
	# device while the blobs sit on snd_hda_scodec_cs35l41 it depends on. One
	# level is enough; deeper deps are shared libs (snd, cs_dsp) with none.
	# modinfo prints dashes here where it answers to underscores.
	deps: set[str] = set()
	for line in _run_splitlines(['modinfo', '-k', release, '-F', 'depends', module]):
		deps.update(d.replace('-', '_') for d in line.split(',') if d)

	return deps


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
	def has_tpm2(self) -> bool:
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

	@cached_property
	def has_bcachefs(self) -> bool:
		# out of tree since 6.18: the stock ISO cannot format or mount it, only
		# a medium built with A2_BCACHEFS=1 registers the filesystem
		try:
			text = _PROC_FILESYSTEMS.read_text()
		except OSError:
			return False
		return any(line.split()[-1] == 'bcachefs' for line in text.splitlines() if line.strip())

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
	def is_portable(self) -> bool:
		return _read_dmi('chassis_type') in _PORTABLE_CHASSIS

	@cached_property
	def module_release(self) -> str:
		return _module_release()

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

	@cached_property
	def gpu_ids(self) -> set[tuple[int, int]]:
		# (vendor, device) of every display-class function (0x03xxxx: VGA, 3D,
		# display). Sysfs rather than lspci text so the device id is usable
		if not _PCI_BUS.is_dir():
			debug('No PCI bus in sysfs; GPU detection unavailable')
			return set()

		found: set[tuple[int, int]] = set()
		for dev in _PCI_BUS.iterdir():
			try:
				if not (dev / 'class').read_text().startswith('0x03'):
					continue
				found.add((int((dev / 'vendor').read_text(), 16), int((dev / 'device').read_text(), 16)))
			except OSError, ValueError:
				continue

		return found

	@cached_property
	def device_modules(self) -> set[str]:
		# bound module (modalias match when unbound) plus one level of depends.
		# Bound only: SOF probes and declines on HDA laptops, yet stays loaded
		release = self.module_release
		bound: set[str] = set()
		for bus in _MODULE_BUSES:
			bound |= _bus_modules(_SYS_BUS / bus / 'devices', release)

		modules = set(bound)
		for module in sorted(bound):
			modules |= _module_depends(release, module)

		return modules

	@cached_property
	def declared_firmware(self) -> set[str]:
		# relative to /usr/lib/firmware, uncompressed, some globs
		release = self.module_release
		declared: set[str] = set()
		for module in sorted(self.device_modules):
			declared.update(_run_splitlines(['modinfo', '-k', release, '-F', 'firmware', module]))

		return declared


_sys_info = _SysInfo()


class SysInfo:
	@staticmethod
	def has_uefi() -> bool:
		return _sys_info.has_uefi

	@staticmethod
	def has_tpm2() -> bool:
		return _sys_info.has_tpm2

	@staticmethod
	def has_bcachefs() -> bool:
		return _sys_info.has_bcachefs

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
	def gpu_ids() -> set[tuple[int, int]]:
		return _sys_info.gpu_ids

	@staticmethod
	def has_nvidia_graphics() -> bool:
		return any(vendor == _PCI_VENDOR_NVIDIA for vendor, _ in _sys_info.gpu_ids)

	@staticmethod
	def has_amd_graphics() -> bool:
		return any(vendor == _PCI_VENDOR_AMD for vendor, _ in _sys_info.gpu_ids)

	@staticmethod
	def has_intel_graphics() -> bool:
		return any(vendor == _PCI_VENDOR_INTEL for vendor, _ in _sys_info.gpu_ids)

	@staticmethod
	def has_hybrid_graphics() -> bool:
		# laptops only: a desktop often keeps its iGPU enabled beside the card
		known = [gpu for gpu in _sys_info.gpu_ids if gpu[0] in _GPU_VENDORS]
		return _sys_info.is_portable and len(known) > 1

	@staticmethod
	def device_modules() -> set[str]:
		# virtio ships no blobs, and the scan costs a modinfo per bound driver
		if SysInfo.is_vm():
			debug('VM detected: skipping device module scan')
			return set()
		return _sys_info.device_modules

	@staticmethod
	def declared_firmware() -> set[str]:
		if SysInfo.is_vm():
			return set()
		return _sys_info.declared_firmware

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
		# the bound one is per platform (snd_sof_pci_intel_tgl), snd_sof sits deeper
		return any(m.startswith('snd_sof') for m in SysInfo.device_modules())

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

		return not SysInfo.device_modules().isdisjoint(modules)
