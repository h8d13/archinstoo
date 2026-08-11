from typing import TYPE_CHECKING

import pytest

from archinstoo.lib import hardware
from archinstoo.lib.models.firmware import (
	FirmwareConfiguration,
	FirmwareType,
	FirmwareVendor,
	detect_optdeps,
	detect_splits,
)

if TYPE_CHECKING:
	from pathlib import Path

# Hard deps of linux-firmware that no bus ID reaches, taken unconditionally
BASELINE = {FirmwareVendor.CIRRUS, FirmwareVendor.OTHER}


def _fake_bus(root: Path, attr: str, ids: list[str]) -> Path:
	# Mirrors sysfs: one directory per device holding a vendor-ID attribute
	root.mkdir(parents=True, exist_ok=True)
	for idx, vendor_id in enumerate(ids):
		dev = root / f'dev{idx}'
		dev.mkdir()
		(dev / attr).write_text(vendor_id + '\n')
	return root


def _reset(monkeypatch: pytest.MonkeyPatch) -> None:
	# detection reads the module singleton, whose probes cache for the process
	monkeypatch.setattr(hardware, '_sys_info', hardware._SysInfo())
	monkeypatch.setattr(hardware.SysInfo, 'is_vm', staticmethod(lambda: False))


def _optdeps(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, pci: list[str], usb: list[str]) -> set[FirmwareVendor]:
	monkeypatch.setattr(hardware, '_PCI_BUS', _fake_bus(tmp_path / 'pci', 'vendor', pci))
	monkeypatch.setattr(hardware, '_USB_BUS', _fake_bus(tmp_path / 'usb', 'idVendor', usb))
	_reset(monkeypatch)

	return set(detect_optdeps())


# -- optional deps: ID table ---------------------------------------------------


@pytest.mark.parametrize(
	('pci', 'usb', 'expected'),
	[
		(['0x11ab'], [], {FirmwareVendor.MARVELL}),
		(['0x1b4b'], [], {FirmwareVendor.MARVELL}),
		([], ['1286'], {FirmwareVendor.MARVELL}),
		(['0x15b3'], [], {FirmwareVendor.MELLANOX}),
		(['0x19ee'], [], {FirmwareVendor.NFP}),
		(['0x177d'], [], {FirmwareVendor.LIQUIDIO}),
		(['0x1077'], [], {FirmwareVendor.QLOGIC}),
		# both Marvell ranges on one host collapse to one package
		(['0x11ab', '0x1b4b'], ['1286'], {FirmwareVendor.MARVELL}),
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
	expected: set[FirmwareVendor],
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
	_reset(monkeypatch)

	assert set(detect_optdeps()) == {FirmwareVendor.MARVELL}


# -- hard-dep splits: kernel + pacman ------------------------------------------


def _fake_driver_bus(root: Path, devices: dict[str, str | None]) -> Path:
	# name -> module when bound, None for an unbound device with only a MODALIAS
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
	# the 0x17cb case: ath11k blobs ship in -atheros, not -qcom
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
	_reset(monkeypatch)

	assert set(detect_splits()) == BASELINE | {FirmwareVendor.ATHEROS}


def test_splits_match_zst_and_collapse_flat_entries(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
	# modinfo reports uncompressed names; disk holds .zst
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
	_reset(monkeypatch)

	assert set(detect_splits()) == BASELINE | {FirmwareVendor.INTEL}

	pacman = next(c for c in calls if c[0] == 'pacman')
	assert pacman[2:] == [str(root / 'iwlwifi-100-5.ucode.zst')]


def test_splits_drop_non_split_owners(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
	# sof-firmware also lives under /usr/lib/firmware
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
	_reset(monkeypatch)

	assert set(detect_splits()) == BASELINE


def test_splits_survive_modules_declaring_no_firmware(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
	# rtw88/rtw89/btusb build their filenames at runtime and declare nothing
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
	_reset(monkeypatch)

	assert set(detect_splits()) == BASELINE


def test_splits_use_module_name_not_driver_name(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
	# i801_smbus is the driver directory, i2c_i801 the module modinfo answers to
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
	_reset(monkeypatch)

	assert set(detect_splits()) == BASELINE
	assert [c[-1] for c in calls if c[0] == 'modinfo'] == ['i2c_i801']


def test_split_scan_skipped_on_vm(monkeypatch: pytest.MonkeyPatch) -> None:
	monkeypatch.setattr(hardware, '_sys_info', hardware._SysInfo())
	monkeypatch.setattr(hardware.SysInfo, 'is_vm', staticmethod(lambda: True))

	assert hardware.SysInfo.firmware_owners() == []
	assert set(detect_splits()) == BASELINE


# -- wiring --------------------------------------------------------------------


def test_is_vm_forks_once(monkeypatch: pytest.MonkeyPatch) -> None:
	# gates the firmware scan, microcode and the gfx driver list
	calls: list[str] = []

	def fake_syscommand(cmd: str) -> list[bytes]:
		calls.append(cmd)
		return [b'none']

	monkeypatch.setattr(hardware, 'SysCommand', fake_syscommand)
	info = hardware._SysInfo()

	assert (info.is_vm, info.is_vm, info.is_vm) == (False, False, False)
	assert calls == ['systemd-detect-virt']


@pytest.mark.parametrize(
	('is_vm', 'expected'),
	[
		(True, FirmwareType.MINIMAL),
		(False, FirmwareType.FULL),
	],
)
def test_firmware_default_per_host(monkeypatch: pytest.MonkeyPatch, is_vm: bool, expected: FirmwareType) -> None:
	monkeypatch.setattr(hardware.SysInfo, 'is_vm', staticmethod(lambda: is_vm))

	assert FirmwareConfiguration.default().firmware_type is expected


@pytest.mark.parametrize(
	('config', 'optdeps', 'expected'),
	[
		# FULL used to stop at the metapackage
		(FirmwareConfiguration(), [], ['linux-firmware']),
		(
			FirmwareConfiguration(),
			[FirmwareVendor.MARVELL],
			['linux-firmware', 'linux-firmware-marvell'],
		),
		# MINIMAL is an explicit opt-out and stays empty even with a match
		(
			FirmwareConfiguration(firmware_type=FirmwareType.MINIMAL),
			[FirmwareVendor.MARVELL],
			[],
		),
		(
			FirmwareConfiguration(firmware_type=FirmwareType.VENDOR, vendors=[FirmwareVendor.INTEL]),
			[FirmwareVendor.MARVELL],
			['linux-firmware-intel'],
		),
	],
)
def test_firmware_packages(
	monkeypatch: pytest.MonkeyPatch,
	config: FirmwareConfiguration,
	optdeps: list[FirmwareVendor],
	expected: list[str],
) -> None:
	monkeypatch.setattr('archinstoo.lib.models.firmware.detect_optdeps', lambda: optdeps)

	assert config.packages() == expected
