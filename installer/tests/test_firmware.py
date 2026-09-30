import os
import shutil
import subprocess
import sys
from typing import TYPE_CHECKING, ClassVar

import pytest

from archinstoo.lib import hardware
from archinstoo.lib.models.firmware import FIRMWARE_OPTDEPS, FirmwareConfiguration, FirmwareType, FirmwareVendor
from archinstoo.lib.pm import firmware as firmware_pm

if TYPE_CHECKING:
	from collections.abc import Iterator
	from pathlib import Path

BASELINE = {FirmwareVendor.OTHER}

_REAL_INDEX = firmware_pm.firmware_index


@pytest.fixture(autouse=True)
def _no_files_db(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
	# no test may reach a mirror
	firmware_pm._detected.cache_clear()
	monkeypatch.setattr(firmware_pm, 'firmware_index', dict)
	yield
	firmware_pm._detected.cache_clear()
	_REAL_INDEX.cache_clear()


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


def _driver_buses(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, buses: dict[str, dict[str, str | None]]) -> None:
	root = tmp_path / 'bus'
	root.mkdir()
	for bus, devices in buses.items():
		_fake_driver_bus(root / bus / 'devices', devices)
	monkeypatch.setattr(hardware, '_SYS_BUS', root)


def _stub_run(
	monkeypatch: pytest.MonkeyPatch,
	firmware: dict[str, list[str]] | None = None,
	depends: dict[str, str] | None = None,
) -> list[list[str]]:
	calls: list[list[str]] = []
	firmware = firmware or {}
	depends = depends or {}

	def fake_run(cmd: list[str]) -> list[str]:
		calls.append(cmd)
		match cmd[0]:
			case 'modinfo' if cmd[-2] == 'depends':
				# modinfo prints one comma-joined line, dashes not underscores
				return [depends[cmd[-1]]] if cmd[-1] in depends else []
			case 'modinfo':
				return firmware.get(cmd[-1], [])
			case _:
				# unbound devices in these fixtures resolve to nothing
				return []

	monkeypatch.setattr(hardware, '_run_splitlines', fake_run)
	monkeypatch.setattr(hardware, '_module_release', lambda: '0-test')
	return calls


def _host(monkeypatch: pytest.MonkeyPatch, index: dict[str, str] | None = None) -> list[int]:
	monkeypatch.setattr(hardware, '_sys_info', hardware._SysInfo())
	monkeypatch.setattr(hardware.SysInfo, 'is_vm', staticmethod(lambda: False))
	asked: list[int] = []

	def fake_index() -> dict[str, str]:
		asked.append(1)
		return index or {}

	monkeypatch.setattr(firmware_pm, 'firmware_index', fake_index)
	return asked


# -- splits: declared name -> owning package ------------------------------------


def test_globs_resolve_through_the_index(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
	# the 0x17cb case: ath11k blobs ship in -atheros, not -qcom
	_driver_buses(monkeypatch, tmp_path, {'pci': {'0000:00:01.0': 'ath11k_pci'}})
	_stub_run(monkeypatch, firmware={'ath11k_pci': ['ath11k/WCN6855/hw2.0/*']})
	_host(monkeypatch, {'ath11k/WCN6855/hw2.0/board-2.bin': 'linux-firmware-atheros'})

	assert set(firmware_pm.detect_splits()) == BASELINE | {FirmwareVendor.ATHEROS}


def test_flat_names_resolve_one_by_one(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
	# ti_usb_3410_5052 mixes moxa/, flat mts_* (-other) and flat ti_* (-ti)
	_driver_buses(monkeypatch, tmp_path, {'usb': {'1-2': 'ti_usb_3410_5052'}})
	_stub_run(monkeypatch, firmware={'ti_usb_3410_5052': ['moxa/moxa-1151.fw', 'mts_edge.fw', 'ti_3410.fw']})
	_host(
		monkeypatch,
		{
			'moxa/moxa-1151.fw': 'linux-firmware-other',
			'mts_edge.fw': 'linux-firmware-other',
			'ti_3410.fw': 'linux-firmware-ti',
		},
	)

	assert set(firmware_pm.detect_splits()) == BASELINE | {FirmwareVendor.TI}


def test_owners_outside_the_enum_drop(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
	_driver_buses(monkeypatch, tmp_path, {'pci': {'0000:00:18.3': 'k10temp'}})
	_stub_run(monkeypatch, firmware={'k10temp': ['amd-ucode/microcode_amd.bin', 'regulatory.db', 'new/blob.bin']})
	_host(
		monkeypatch,
		{
			'amd-ucode/microcode_amd.bin': 'amd-ucode',
			'regulatory.db': 'wireless-regdb',
			'new/blob.bin': 'linux-firmware-new',
		},
	)

	assert set(firmware_pm.detect_splits()) == BASELINE


def test_nothing_declared_never_syncs(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
	# rtw88_8822be declares nothing itself (its rtw88_8822b depend does)
	_driver_buses(monkeypatch, tmp_path, {'pci': {'0000:00:02.0': 'rtw88_8822be', '0000:00:03.0': None}})
	_stub_run(monkeypatch)
	asked = _host(monkeypatch)

	assert set(firmware_pm.detect_splits()) == BASELINE
	assert asked == []


def test_splits_use_module_name_not_driver_name(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
	# i801_smbus is the driver directory, i2c_i801 the module modinfo answers to
	_driver_buses(monkeypatch, tmp_path, {'pci': {'0000:00:1f.4': 'i2c_i801'}})
	calls = _stub_run(monkeypatch)
	_host(monkeypatch)

	assert set(firmware_pm.detect_splits()) == BASELINE
	assert {c[-1] for c in calls if c[0] == 'modinfo'} == {'i2c_i801'}


def test_splits_reach_acpi_amps_through_wrapper_depends(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
	# CS35L41 sits on the ACPI bus, binds through the _i2c wrapper, and the
	# wrapper declares no firmware: the blobs are on the parent it depends on
	_driver_buses(monkeypatch, tmp_path, {'acpi': {'CSC3551:00': 'snd_hda_scodec_cs35l41_i2c'}})
	_stub_run(
		monkeypatch,
		firmware={'snd_hda_scodec_cs35l41': ['cirrus/cs35l41-*.bin', 'cirrus/cs35l41-*.wmfw']},
		depends={'snd_hda_scodec_cs35l41_i2c': 'snd-hda-scodec-cs35l41,snd-soc-cs35l41-lib'},
	)
	_host(monkeypatch, {'cirrus/cs35l41-dsp1-spk-prot-10280c05.wmfw': 'linux-firmware-cirrus'})

	assert set(firmware_pm.detect_splits()) == BASELINE | {FirmwareVendor.CIRRUS}


def test_splits_skip_cirrus_without_amp(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
	# Realtek-only codec (Latitude 5540): no ACPI amp node, no cirrus split
	_driver_buses(monkeypatch, tmp_path, {'pci': {'0000:00:1f.3': 'snd_hda_intel'}, 'acpi': {'PNP0C09:00': 'ec'}})
	_stub_run(monkeypatch)
	_host(monkeypatch, {'cirrus/cs35l41-dsp1-spk-prot-10280c05.wmfw': 'linux-firmware-cirrus'})

	assert set(firmware_pm.detect_splits()) == BASELINE


def test_splits_reach_sdio_wifi(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
	_driver_buses(monkeypatch, tmp_path, {'sdio': {'mmc1:0001:1': 'brcmfmac'}})
	_stub_run(monkeypatch, firmware={'brcmfmac': ['brcm/brcmfmac43455-sdio.bin']})
	_host(monkeypatch, {'brcm/brcmfmac43455-sdio.bin': 'linux-firmware-broadcom'})

	assert set(firmware_pm.detect_splits()) == BASELINE | {FirmwareVendor.BROADCOM}


def test_split_scan_skipped_on_vm(monkeypatch: pytest.MonkeyPatch) -> None:
	asked = _host(monkeypatch)
	monkeypatch.setattr(hardware.SysInfo, 'is_vm', staticmethod(lambda: True))

	assert set(firmware_pm.detect_splits()) == BASELINE
	assert asked == []


# -- optdeps: the detected splits linux-firmware leaves out --------------------


@pytest.mark.parametrize(
	('module', 'declared', 'owner', 'optdeps'),
	[
		('mwifiex_pcie', 'mrvl/pcie8897_uapsta.bin', 'linux-firmware-marvell', [FirmwareVendor.MARVELL]),
		('qla2xxx', 'ql2500_fw.bin', 'linux-firmware-qlogic', [FirmwareVendor.QLOGIC]),
		('iwlwifi', 'iwlwifi-cc-a0-77.ucode', 'linux-firmware-intel', []),
	],
)
def test_optdeps_come_from_ownership(
	monkeypatch: pytest.MonkeyPatch,
	tmp_path: Path,
	module: str,
	declared: str,
	owner: str,
	optdeps: list[FirmwareVendor],
) -> None:
	_driver_buses(monkeypatch, tmp_path, {'pci': {'0000:03:00.0': module}})
	_stub_run(monkeypatch, firmware={module: [declared]})
	_host(monkeypatch, {declared: owner})

	assert firmware_pm.detect_optdeps() == optdeps
	assert firmware_pm.firmware_packages(FirmwareConfiguration()) == ['linux-firmware', *(v.value for v in optdeps)]


# -- the index: core's files db ------------------------------------------------


class _FakeDB:
	synced: ClassVar[bool] = True
	listing: ClassVar[list[tuple[str, str]]] = []

	def __init__(self, repos: tuple[str, ...]) -> None:
		assert repos == ('core',)

	def sync_files(self) -> bool:
		return self.synced

	def files(self) -> list[tuple[str, str]]:
		return self.listing


def test_index_keys_match_modinfo_names(monkeypatch: pytest.MonkeyPatch) -> None:
	monkeypatch.setattr(sys, 'argv', ['archinstoo'])
	monkeypatch.setattr(_FakeDB, 'listing', [('linux-firmware-ti', 'usr/lib/firmware/ti_3410.fw.zst'), ('bash', 'usr/bin/bash')])
	monkeypatch.setattr(firmware_pm, 'TmpDB', _FakeDB)
	_REAL_INDEX.cache_clear()

	assert _REAL_INDEX() == {'ti_3410.fw': 'linux-firmware-ti'}


def test_failed_sync_leaves_no_index(monkeypatch: pytest.MonkeyPatch) -> None:
	monkeypatch.setattr(sys, 'argv', ['archinstoo'])
	monkeypatch.setattr(_FakeDB, 'synced', False)
	monkeypatch.setattr(firmware_pm, 'TmpDB', _FakeDB)
	_REAL_INDEX.cache_clear()

	assert _REAL_INDEX() == {}


def test_offline_never_touches_a_mirror(monkeypatch: pytest.MonkeyPatch) -> None:
	def refuse(_: tuple[str, ...]) -> None:
		raise AssertionError('offline must not build a files db')

	monkeypatch.setattr(sys, 'argv', ['archinstoo', '--offline'])
	monkeypatch.setattr(firmware_pm, 'TmpDB', refuse)
	_REAL_INDEX.cache_clear()

	assert _REAL_INDEX() == {}


def _si_field(text: str, key: str) -> set[str]:
	# 'Key   : a  b', continuation lines indented, optdeps as 'name: description'
	values: set[str] = set()
	current = ''
	for line in text.splitlines():
		head, sep, rest = line.partition(' : ')
		if sep and not line.startswith(' '):
			current = head.strip()
		if current == key:
			values.update(token.rstrip(':') for token in (rest if sep else line).split())
	return {v for v in values if v.startswith('linux-firmware-')}


def test_enum_matches_arch_metadata() -> None:
	# the enum is hand kept, a split Arch adds (amd, ti) fails here
	if not shutil.which('pacman'):
		pytest.skip('no pacman')
	# C locale: the field labels are translated otherwise
	proc = subprocess.run(
		['pacman', '-Si', 'linux-firmware'],  # noqa: S607 - pacman from $PATH
		capture_output=True,
		text=True,
		check=False,
		env={**os.environ, 'LC_ALL': 'C'},
	)
	if proc.returncode != 0:
		pytest.skip(f'no synced db: {proc.stderr.strip()}')

	depends = _si_field(proc.stdout, 'Depends On') - {'linux-firmware-whence'}
	optdeps = _si_field(proc.stdout, 'Optional Deps')

	assert {v.value for v in FIRMWARE_OPTDEPS} == optdeps
	assert {v.value for v in FirmwareVendor} == depends | optdeps


# -- hardware probes -------------------------------------------------------------


def test_modprobe_resolves_against_target_release(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
	# after an upgrade without reboot the running kernel's modules are gone
	_driver_buses(monkeypatch, tmp_path, {'pci': {'0000:00:03.0': None}})
	calls = _stub_run(monkeypatch)
	_host(monkeypatch)

	hardware.SysInfo.device_modules()

	assert [c for c in calls if c[0] == 'modprobe'] == [['modprobe', '-S', '0-test', '-R', 'pci:v00000000:00:03.0d0']]


@pytest.mark.parametrize(
	('buses', 'depends', 'sof', 'alsa'),
	[
		# SOF probes and declines on HDA-only laptops, snd_hda_intel binds
		({'pci': {'0000:00:1f.3': 'snd_hda_intel'}}, {}, False, False),
		({'pci': {'0000:00:1f.3': 'snd_sof_pci_intel_tgl'}}, {}, True, False),
		({'pci': {'0000:04:00.5': 'snd_sof_amd_rembrandt'}}, {}, True, False),
		({'pci': {'0000:00:1f.3': 'snd_hda_intel'}, 'hdaudio': {'hdaudioC0D0': 'snd_hda_codec_ca0132'}}, {}, False, True),
		({'pci': {'0000:05:00.0': 'snd_vx222'}}, {'snd_vx222': 'snd-vx-lib,snd-pcm'}, False, True),
	],
)
def test_sound_firmware_from_device_modules(
	monkeypatch: pytest.MonkeyPatch,
	tmp_path: Path,
	buses: dict[str, dict[str, str | None]],
	depends: dict[str, str],
	sof: bool,
	alsa: bool,
) -> None:
	_driver_buses(monkeypatch, tmp_path, buses)
	_stub_run(monkeypatch, depends=depends)
	_host(monkeypatch)

	assert (hardware.SysInfo.requires_sof_fw(), hardware.SysInfo.requires_alsa_fw()) == (sof, alsa)


def test_sound_firmware_skipped_on_vm(monkeypatch: pytest.MonkeyPatch) -> None:
	monkeypatch.setattr(hardware, '_sys_info', hardware._SysInfo())
	monkeypatch.setattr(hardware.SysInfo, 'is_vm', staticmethod(lambda: True))

	assert not hardware.SysInfo.requires_sof_fw()
	assert not hardware.SysInfo.requires_alsa_fw()


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


# -- configuration ---------------------------------------------------------------


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
	monkeypatch.setattr(firmware_pm, 'detect_optdeps', lambda: optdeps)

	assert firmware_pm.firmware_packages(config) == expected
