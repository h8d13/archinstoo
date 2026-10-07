# Host hardware probes behind `--script detect`. Kept off the install path:
# every menu is a pick, this only reports what the host's devices point at

import fnmatch
import platform
import subprocess
from pathlib import Path

from archinstoo.lib.models.firmware import FIRMWARE_OPTDEPS, FirmwareVendor
from archinstoo.lib.models.graphics import GFX_PACKAGES, GfxDriver, GfxPackage
from archinstoo.lib.output import debug
from archinstoo.lib.pm.tmpdb import TmpDB

_PCI_VENDOR_AMD = 0x1002  # ATI's ID, every AMD GPU still carries it
_PCI_VENDOR_INTEL = 0x8086
_PCI_VENDOR_NVIDIA = 0x10DE
_GFX_BY_VENDOR: dict[int, GfxDriver] = {_PCI_VENDOR_AMD: GfxDriver.AmdOpenSource, _PCI_VENDOR_INTEL: GfxDriver.IntelOpenSource}
_GPU_VENDORS: dict[int, str] = {_PCI_VENDOR_AMD: 'amd', _PCI_VENDOR_INTEL: 'intel', _PCI_VENDOR_NVIDIA: 'nvidia'}
# nvidia-open needs the GSP, so Turing on: TU102 opens at 0x1e02 and every
# later generation numbers higher. Volta (GV100, 0x1d81) stays below
_NVIDIA_TURING_FIRST = 0x1E00

# Module-level so tests can point the sweeps at a synthetic tree
_SYS_BUS = Path('/sys/bus')
_PCI_BUS = _SYS_BUS / 'pci/devices'
# amps enumerate on acpi and bind on i2c/spi, codecs on hdaudio, SoC blocks on platform
_MODULE_BUSES = ('pci', 'usb', 'acpi', 'hdaudio', 'i2c', 'platform', 'sdio', 'soundwire', 'spi')
_MODULE_ROOT = Path('/usr/lib/modules')
_DMI_CHASSIS = Path('/sys/class/dmi/id/chassis_type')
# SMBIOS portable chassis: chwd's laptop set plus sub notebook and detachable
_PORTABLE_CHASSIS = frozenset({'8', '9', '10', '11', '14', '31', '32'})
_FIRMWARE_DIR = 'usr/lib/firmware/'


def _run_splitlines(cmd: list[str]) -> list[str]:
	# a nonzero exit from modinfo/modprobe -R only means no answer
	try:
		proc = subprocess.run(cmd, capture_output=True, text=True, check=False)  # noqa: S603 - fixed argv, no user input
	except OSError as err:
		debug(f'{cmd[0]} unavailable: {err}')
		return []

	return [line for line in proc.stdout.splitlines() if line]


def module_release() -> str:
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


def is_portable() -> bool:
	try:
		return _DMI_CHASSIS.read_text().strip() in _PORTABLE_CHASSIS
	except OSError:
		return False


# -- GPUs ------------------------------------------------------------------------


def gpu_ids() -> set[tuple[int, int]]:
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


def gpu_vendors(gpus: set[tuple[int, int]]) -> list[str]:
	# known vendors only: a server's BMC (ASPEED) is display class too
	return sorted({_GPU_VENDORS[vendor] for vendor, _ in gpus if vendor in _GPU_VENDORS})


def gfx_drivers(gpus: set[tuple[int, int]]) -> list[GfxDriver]:
	# one preset per GPU; a hybrid yields two, which only Custom holds at once
	drivers: list[GfxDriver] = []
	for vendor, device in sorted(gpus):
		driver = _GFX_BY_VENDOR.get(vendor)
		if vendor == _PCI_VENDOR_NVIDIA:
			driver = GfxDriver.NvidiaOpenKernel if device >= _NVIDIA_TURING_FIRST else GfxDriver.NvidiaOpenSource
		if driver and driver not in drivers:
			drivers.append(driver)
	return drivers


def is_hybrid(gpus: set[tuple[int, int]], portable: bool) -> bool:
	# laptops only: a desktop often keeps its iGPU enabled beside the card,
	# which then drives the display alone. Same-vendor pairs share a preset
	return portable and len(gfx_drivers(gpus)) > 1


def gfx_packages(gpus: set[tuple[int, int]]) -> list[GfxPackage]:
	# the union of the matching presets, first occurrence wins the order
	packages: list[GfxPackage] = []
	for driver in gfx_drivers(gpus):
		packages += [p for p in GFX_PACKAGES[driver] if p not in packages]
	return packages


# -- device modules --------------------------------------------------------------


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


def _wrapped_parents(release: str, module: str) -> set[str]:
	# Bus wrappers declare no firmware: snd_hda_scodec_cs35l41_i2c binds the
	# device while the blobs sit on snd_hda_scodec_cs35l41, the prefix of its
	# own name. Other depends are link-time only: btusb calls into btintel,
	# btrtl, btmtk and btbcm alike and picks one per device at probe.
	# modinfo prints dashes here where it answers to underscores.
	parents: set[str] = set()
	for line in _run_splitlines(['modinfo', '-k', release, '-F', 'depends', module]):
		deps = (d.replace('-', '_') for d in line.split(',') if d)
		parents.update(d for d in deps if module.startswith(d + '_'))

	return parents


def device_modules(release: str) -> set[str]:
	# bound module (modalias match when unbound) plus the parent it wraps.
	# Bound only: SOF probes and declines on HDA laptops, yet stays loaded
	bound: set[str] = set()
	for bus in _MODULE_BUSES:
		bound |= _bus_modules(_SYS_BUS / bus / 'devices', release)

	modules = set(bound)
	for module in sorted(bound):
		modules |= _wrapped_parents(release, module)

	return modules


def declared_firmware(release: str, modules: set[str]) -> dict[str, set[str]]:
	# module -> names relative to /usr/lib/firmware, uncompressed, some globs.
	# Modules declaring nothing are left out
	declared: dict[str, set[str]] = {}
	for module in sorted(modules):
		if names := _run_splitlines(['modinfo', '-k', release, '-F', 'firmware', module]):
			declared[module] = set(names)

	return declared


# -- firmware ownership ----------------------------------------------------------
# A lower bound, never a full list. Runtime-named firmware goes undetected:
# SOF, tas2781, amdtee, and Bluetooth (btintel declares ibt-12-16 while the
# chip loads ibt-0040-0041, built from its hw/fw variant at setup)


def firmware_index() -> dict[str, str]:
	# blob path -> owning package, from core's files db
	db = TmpDB(('core',))
	if not db.sync_files():
		return {}

	return {path.removeprefix(_FIRMWARE_DIR).removesuffix('.zst'): pkg for pkg, path in db.files() if path.startswith(_FIRMWARE_DIR)}


def owners(declared: set[str], index: dict[str, str]) -> set[str]:
	found: set[str] = set()
	for entry in declared:
		if any(c in entry for c in '*?['):
			found.update(index[path] for path in fnmatch.filter(index, entry))
		elif pkg := index.get(entry):
			found.add(pkg)
	return found


def firmware_splits(declared: dict[str, set[str]], index: dict[str, str]) -> dict[FirmwareVendor, list[str]]:
	# split -> the modules whose declared blobs it ships
	members = {v.value: v for v in FirmwareVendor}
	splits: dict[FirmwareVendor, list[str]] = {}
	for module, names in sorted(declared.items()):
		for pkg in sorted(owners(names, index)):
			if pkg in members:
				splits.setdefault(members[pkg], []).append(module)
			elif pkg.startswith('linux-firmware-'):
				debug(f'Firmware split {pkg} is not a FirmwareVendor member')

	return dict(sorted(splits.items()))


def firmware_optdeps(splits: dict[FirmwareVendor, list[str]]) -> list[FirmwareVendor]:
	# what FULL leaves out: linux-firmware only optdepends on these
	return [v for v in splits if v in FIRMWARE_OPTDEPS]
