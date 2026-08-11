from typing import TYPE_CHECKING

import pytest

from archinstoo.lib import hardware
from archinstoo.lib.hardware import _SysInfo
from archinstoo.lib.models.firmware import FirmwareConfiguration, FirmwareType, FirmwareVendor

if TYPE_CHECKING:
	from pathlib import Path

# Hard deps of linux-firmware that no bus ID reaches, taken unconditionally
BASELINE = {'linux-firmware-cirrus', 'linux-firmware-other'}


def _fake_bus(root: Path, attr: str, ids: list[str]) -> Path:
	# Mirrors sysfs: one directory per device holding a vendor-ID attribute
	root.mkdir(parents=True, exist_ok=True)
	for idx, vendor_id in enumerate(ids):
		dev = root / f'dev{idx}'
		dev.mkdir()
		(dev / attr).write_text(vendor_id + '\n')
	return root


def _optdeps(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, pci: list[str], usb: list[str]) -> set[str]:
	monkeypatch.setattr(hardware, '_PCI_BUS', _fake_bus(tmp_path / 'pci', 'vendor', pci))
	monkeypatch.setattr(hardware, '_USB_BUS', _fake_bus(tmp_path / 'usb', 'idVendor', usb))

	return set(_SysInfo().firmware_optdeps)


# -- optional deps: ID table ---------------------------------------------------
#
# The only IDs archinstoo still owns. pacman never installs these splits, so
# their files are absent and no local lookup can name them.


@pytest.mark.parametrize(
	('pci', 'usb', 'expected'),
	[
		(['0x11ab'], [], {'linux-firmware-marvell'}),
		(['0x1b4b'], [], {'linux-firmware-marvell'}),
		([], ['1286'], {'linux-firmware-marvell'}),
		(['0x15b3'], [], {'linux-firmware-mellanox'}),
		(['0x19ee'], [], {'linux-firmware-nfp'}),
		(['0x177d'], [], {'linux-firmware-liquidio'}),
		(['0x1077'], [], {'linux-firmware-qlogic'}),
		# both Marvell ranges on one host collapse to one package
		(['0x11ab', '0x1b4b'], ['1286'], {'linux-firmware-marvell'}),
		# hard-dep vendors are NOT in this table: linux-firmware already has them
		(['0x10de', '0x8086', '0x1002', '0x17cb'], ['0bda', '8087'], set()),
		# root hub, Samsung NVMe, ASMedia: nothing to pull
		([], ['1d6b'], set()),
		(['0x144d', '0x1b21'], [], set()),
	],
)
def test_optdep_detection(
	monkeypatch: pytest.MonkeyPatch,
	tmp_path: Path,
	pci: list[str],
	usb: list[str],
	expected: set[str],
) -> None:
	assert _optdeps(monkeypatch, tmp_path, pci, usb) == expected


def test_optdeps_empty_without_any_device(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
	assert _optdeps(monkeypatch, tmp_path, [], []) == set()


def test_optdeps_skip_devices_without_vendor_attr(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
	# USB interface nodes (1-1:1.0) carry no idVendor and must not abort the sweep
	usb = _fake_bus(tmp_path / 'usb', 'idVendor', ['1286'])
	(usb / '1-1:1.0').mkdir()

	monkeypatch.setattr(hardware, '_PCI_BUS', tmp_path / 'absent')
	monkeypatch.setattr(hardware, '_USB_BUS', usb)

	assert set(_SysInfo().firmware_optdeps) == {'linux-firmware-marvell'}


# -- hard-dep splits: kernel + pacman ------------------------------------------


def _fake_driver_bus(root: Path, devices: dict[str, str | None]) -> Path:
	# name -> module for bound devices, or None for an unbound device carrying
	# only a MODALIAS. Mirrors the two shapes _bus_modules has to handle.
	root.mkdir(parents=True, exist_ok=True)
	modules = root.parent / 'modules'
	modules.mkdir(exist_ok=True)

	for name, module in devices.items():
		dev = root / name
		dev.mkdir()
		if module is None:
			(dev / 'uevent').write_text(f'DRIVER=\nMODALIAS=pci:v0000{name}d0\n')
			continue

		(modules / module).mkdir(exist_ok=True)
		driver = dev / 'driver'
		driver.mkdir()
		(driver / 'module').symlink_to(modules / module)

	return root


def _stub_run(monkeypatch: pytest.MonkeyPatch, firmware: dict[str, list[str]], owners: dict[str, str]) -> list[list[str]]:
	calls: list[list[str]] = []

	def fake_run(cmd: list[str]) -> list[str]:
		calls.append(cmd)
		match cmd[0]:
			case 'modinfo':
				return firmware.get(cmd[-1], [])
			case 'modprobe':
				# unbound devices in these fixtures resolve to nothing
				return []
			case 'pacman':
				return sorted({owners[p] for p in cmd[2:] if p in owners})
			case _:
				return []

	monkeypatch.setattr(hardware, '_run', fake_run)
	monkeypatch.setattr(hardware, '_module_release', lambda: '0-test')
	return calls


def test_splits_resolve_through_module_and_owner(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
	# The 0x17cb case the old ID table got right only by hand: ath11k blobs ship
	# in -atheros, not -qcom, and nothing here has to know that.
	root = tmp_path / 'fw'
	(root / 'ath11k/WCN6855/hw2.0').mkdir(parents=True)
	(root / 'ath11k/WCN6855/hw2.0/board-2.bin.zst').write_text('')

	monkeypatch.setattr(hardware, '_PCI_BUS', _fake_driver_bus(tmp_path / 'pci', {'0000:00:01.0': 'ath11k_pci'}))
	monkeypatch.setattr(hardware, '_USB_BUS', tmp_path / 'absent')
	monkeypatch.setattr(hardware, '_FIRMWARE_ROOT', root)
	_stub_run(
		monkeypatch,
		firmware={'ath11k_pci': ['ath11k/WCN6855/hw2.0/*']},
		owners={str(root / 'ath11k/WCN6855/hw2.0/board-2.bin.zst'): 'linux-firmware-atheros'},
	)

	assert set(_SysInfo().firmware_splits) == BASELINE | {'linux-firmware-atheros'}


def test_splits_match_zst_and_collapse_flat_entries(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
	# modinfo reports uncompressed names; disk holds .zst. iwlwifi declares ~200
	# flat files, and one resolved lookup has to be enough to name the package.
	root = tmp_path / 'fw'
	root.mkdir()
	for ucode in ('iwlwifi-100-5.ucode', 'iwlwifi-cc-a0-77.ucode'):
		(root / f'{ucode}.zst').write_text('')

	monkeypatch.setattr(hardware, '_PCI_BUS', _fake_driver_bus(tmp_path / 'pci', {'0000:00:14.3': 'iwlwifi'}))
	monkeypatch.setattr(hardware, '_USB_BUS', tmp_path / 'absent')
	monkeypatch.setattr(hardware, '_FIRMWARE_ROOT', root)
	calls = _stub_run(
		monkeypatch,
		firmware={'iwlwifi': ['iwlwifi-100-5.ucode', 'iwlwifi-cc-a0-77.ucode']},
		owners={str(root / 'iwlwifi-100-5.ucode.zst'): 'linux-firmware-intel'},
	)

	assert set(_SysInfo().firmware_splits) == BASELINE | {'linux-firmware-intel'}

	pacman = next(c for c in calls if c[0] == 'pacman')
	assert pacman[2:] == [str(root / 'iwlwifi-100-5.ucode.zst')]


def test_splits_drop_non_split_owners(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
	# sof-firmware and the proprietary nvidia tree also live under
	# /usr/lib/firmware; the caller can only resolve linux-firmware-* splits
	root = tmp_path / 'fw'
	(root / 'intel/sof').mkdir(parents=True)
	(root / 'intel/sof/blob.ri').write_text('')

	monkeypatch.setattr(hardware, '_PCI_BUS', _fake_driver_bus(tmp_path / 'pci', {'0000:00:1f.3': 'snd_sof_pci'}))
	monkeypatch.setattr(hardware, '_USB_BUS', tmp_path / 'absent')
	monkeypatch.setattr(hardware, '_FIRMWARE_ROOT', root)
	_stub_run(
		monkeypatch,
		firmware={'snd_sof_pci': ['intel/sof/blob.ri']},
		owners={str(root / 'intel/sof/blob.ri'): 'sof-firmware'},
	)

	assert set(_SysInfo().firmware_splits) == BASELINE


def test_splits_survive_modules_declaring_no_firmware(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
	# rtw88/rtw89/btusb build their filenames at runtime and declare nothing.
	# FULL covers them from the metapackage, so this may only shrink a trim.
	root = tmp_path / 'fw'
	root.mkdir()

	monkeypatch.setattr(
		hardware,
		'_PCI_BUS',
		_fake_driver_bus(tmp_path / 'pci', {'0000:00:02.0': 'rtw88_8822be', '0000:00:03.0': None}),
	)
	monkeypatch.setattr(hardware, '_USB_BUS', tmp_path / 'absent')
	monkeypatch.setattr(hardware, '_FIRMWARE_ROOT', root)
	_stub_run(monkeypatch, firmware={}, owners={})

	assert set(_SysInfo().firmware_splits) == BASELINE


def test_splits_use_module_name_not_driver_name(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
	# i801_smbus is a driver directory; the module is i2c_i801, and modinfo only
	# answers to the latter. Resolution has to go through the module symlink.
	root = tmp_path / 'fw'
	root.mkdir()
	bus = tmp_path / 'pci'
	bus.mkdir()
	modules = tmp_path / 'modules'
	modules.mkdir()
	(modules / 'i2c_i801').mkdir()
	dev = bus / '0000:00:1f.4'
	(dev / 'driver').mkdir(parents=True)
	(dev / 'driver' / 'module').symlink_to(modules / 'i2c_i801')

	monkeypatch.setattr(hardware, '_PCI_BUS', bus)
	monkeypatch.setattr(hardware, '_USB_BUS', tmp_path / 'absent')
	monkeypatch.setattr(hardware, '_FIRMWARE_ROOT', root)
	calls = _stub_run(monkeypatch, firmware={}, owners={})

	assert set(_SysInfo().firmware_splits) == BASELINE
	assert [c[-1] for c in calls if c[0] == 'modinfo'] == ['i2c_i801']


# -- wiring --------------------------------------------------------------------


def test_detected_packages_resolve_to_vendors(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
	# Both sweeps emit bare package names, so every one has to be an enum value
	# on the caller's side. This is the drift guard for the strings in hardware.py.
	assert {v.value for v in FirmwareVendor} >= BASELINE

	detected = _optdeps(monkeypatch, tmp_path, ['0x11ab', '0x15b3', '0x19ee', '0x177d', '0x1077'], ['1286'])

	assert [FirmwareVendor(pkg) for pkg in detected]


@pytest.mark.parametrize(
	('is_vm', 'expected'),
	[
		(True, FirmwareType.MINIMAL),
		(False, FirmwareType.FULL),
	],
)
def test_firmware_default_per_host(monkeypatch: pytest.MonkeyPatch, is_vm: bool, expected: FirmwareType) -> None:
	monkeypatch.setattr('archinstoo.lib.hardware.SysInfo.is_vm', staticmethod(lambda: is_vm))

	assert FirmwareConfiguration.default().firmware_type is expected


def test_split_scan_skipped_on_vm(monkeypatch: pytest.MonkeyPatch) -> None:
	monkeypatch.setattr('archinstoo.lib.hardware.SysInfo.is_vm', staticmethod(lambda: True))

	assert hardware.SysInfo.firmware_split_packages() == []


def test_is_vm_forks_once(monkeypatch: pytest.MonkeyPatch) -> None:
	# is_vm gates the firmware scan, microcode and the gfx driver list, and it
	# forks systemd-detect-virt. Uncached it put that fork on every caller.
	calls: list[str] = []

	def fake_syscommand(cmd: str) -> list[bytes]:
		calls.append(cmd)
		return [b'none']

	monkeypatch.setattr(hardware, 'SysCommand', fake_syscommand)
	info = _SysInfo()

	assert (info.is_vm, info.is_vm, info.is_vm) == (False, False, False)
	assert calls == ['systemd-detect-virt']


@pytest.mark.parametrize(
	('config', 'optdeps', 'expected'),
	[
		# the gap: FULL used to stop at the metapackage, leaving a Marvell
		# laptop with no mrvl blobs and no NIC to fix it from
		(FirmwareConfiguration(), [], ['linux-firmware']),
		(
			FirmwareConfiguration(),
			['linux-firmware-marvell'],
			['linux-firmware', 'linux-firmware-marvell'],
		),
		# MINIMAL is an explicit opt-out and stays empty even with a match
		(
			FirmwareConfiguration(firmware_type=FirmwareType.MINIMAL),
			['linux-firmware-marvell'],
			[],
		),
		(
			FirmwareConfiguration(firmware_type=FirmwareType.VENDOR, vendors=[FirmwareVendor.INTEL]),
			['linux-firmware-marvell'],
			['linux-firmware-intel'],
		),
	],
)
def test_firmware_packages(
	monkeypatch: pytest.MonkeyPatch,
	config: FirmwareConfiguration,
	optdeps: list[str],
	expected: list[str],
) -> None:
	monkeypatch.setattr(
		'archinstoo.lib.hardware.SysInfo.firmware_optdep_packages',
		staticmethod(lambda: optdeps),
	)

	assert config.packages() == expected
