# Report what this host's hardware points at: graphics presets, firmware
# splits, microcode. Read-only, nothing feeds the menus; pick from it by hand.
#
# Firmware ownership comes from core's files db, synced into a private dbpath
# (fakeroot when not root). --offline skips it.
# Usage: archinstoo --script detect

from archinstoo.lib import detect
from archinstoo.lib.args import get_arch_config_handler
from archinstoo.lib.hardware import SysInfo


def _row(key: str, value: object) -> None:
	print(f'  {key:<14}{value}')


def _host() -> None:
	print('Host')
	_row('arch', SysInfo.arch())
	_row('cpu', SysInfo.cpu_model() or 'unknown')
	_row('microcode', SysInfo.ucode() or 'none')
	bitness = SysInfo.bitness()
	uefi = f'UEFI {bitness}-bit' if bitness else 'UEFI'
	_row('firmware', uefi if SysInfo.has_uefi() else 'BIOS')
	_row('vm', SysInfo.is_vm())
	_row('portable', detect.is_portable())
	_row('battery', SysInfo.has_battery())
	_row('thunderbolt', SysInfo.has_thunderbolt())


def _graphics() -> None:
	gpus = detect.gpu_ids()
	drivers = detect.gfx_drivers(gpus)

	print('\nGraphics')
	_row('devices', ', '.join(f'{v:04x}:{d:04x}' for v, d in sorted(gpus)) or 'none')
	_row('vendors', ', '.join(detect.gpu_vendors(gpus)) or 'none')
	_row('driver', ', '.join(d.value for d in drivers) or 'none')
	# a hybrid needs both halves, which no single preset holds
	if len(drivers) > 1:
		_row('custom', ' '.join(p.value for p in detect.gfx_packages(gpus)))


def _firmware(offline: bool) -> None:
	print('\nFirmware')
	_row('sof', SysInfo.requires_sof_fw())
	_row('alsa', SysInfo.requires_alsa_fw())

	# virtio ships no blobs, and the scan costs a modinfo per bound driver
	if SysInfo.is_vm():
		_row('splits', 'skipped (VM)')
		return

	release = detect.module_release()
	_row('kernel', release)
	declared = detect.declared_firmware(release, detect.device_modules(release))

	if offline:
		_row('splits', 'skipped (--offline)')
		return

	if not declared:
		_row('splits', 'none declared')
		return

	if not (index := detect.firmware_index()):
		_row('splits', 'files db unavailable, see the log')
		return

	splits = detect.firmware_splits(declared, index)
	_row('optdeps', ' '.join(detect.firmware_optdeps(splits)) or 'none')
	if not splits:
		_row('splits', 'none')
		return

	# which bound modules declare blobs the split ships
	print('  splits')
	for split, modules in splits.items():
		print(f'    {split:<26}{", ".join(modules)}')


def detect_hw() -> None:
	offline = get_arch_config_handler().args.offline
	_host()
	_graphics()
	_firmware(offline)


detect_hw()
