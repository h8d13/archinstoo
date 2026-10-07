# `--script detect` probes: GPU ids off sysfs, bound device modules, and the
# declared firmware resolved to its owning split through core's files db.
from typing import TYPE_CHECKING, ClassVar

import pytest

from archinstoo.lib import detect
from archinstoo.lib.models.firmware import FirmwareVendor
from archinstoo.lib.models.graphics import GFX_PACKAGES, GfxDriver, GfxPackage

if TYPE_CHECKING:
	from pathlib import Path

RELEASE = '0-test'


def _fake_gpus(tmp_path: Path, functions: list[tuple[str, str, str]]) -> Path:
	bus = tmp_path / 'pci'
	for index, (cls, vendor, device) in enumerate(functions):
		dev = bus / f'0000:0{index}:00.0'
		dev.mkdir(parents=True)
		(dev / 'class').write_text(cls + '\n')
		(dev / 'vendor').write_text(vendor + '\n')
		(dev / 'device').write_text(device + '\n')
	return bus


def test_gpu_ids_keep_display_functions_only(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
	# hybrid dGPUs often report as Display controller (0x0380)
	bus = _fake_gpus(
		tmp_path,
		[
			('0x030000', '0x10de', '0x2208'),  # GA102, VGA
			('0x038000', '0x1002', '0x73ff'),  # Navi 23 mobile, Display controller
			('0x0c0330', '0x8086', '0x7ae0'),  # xHCI, not a GPU
		],
	)
	monkeypatch.setattr(detect, '_PCI_BUS', bus)
	assert detect.gpu_ids() == {(0x10DE, 0x2208), (0x1002, 0x73FF)}


def test_gpu_ids_empty_without_a_bus(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
	monkeypatch.setattr(detect, '_PCI_BUS', tmp_path / 'absent')
	assert detect.gpu_ids() == set()


@pytest.mark.parametrize(
	('gpus', 'drivers'),
	[
		# intel + turing-or-later nvidia: the hybrid laptop case (vendor id order)
		({(0x8086, 0xA7A0), (0x10DE, 0x2208)}, [GfxDriver.NvidiaOpenKernel, GfxDriver.IntelOpenSource]),
		# amd + pascal nvidia: the old card lands on nouveau
		({(0x1002, 0x164E), (0x10DE, 0x1B80)}, [GfxDriver.AmdOpenSource, GfxDriver.NvidiaOpenSource]),
		# volta is the last one below the line, TU102 the first above
		({(0x10DE, 0x1D81)}, [GfxDriver.NvidiaOpenSource]),
		({(0x10DE, 0x1E02)}, [GfxDriver.NvidiaOpenKernel]),
		# two of a kind collapse, an unknown vendor (virtio) adds nothing
		({(0x1002, 0x164E), (0x1002, 0x744C), (0x1AF4, 0x1050)}, [GfxDriver.AmdOpenSource]),
		(set(), []),
	],
)
def test_drivers_per_gpu(gpus: set[tuple[int, int]], drivers: list[GfxDriver]) -> None:
	assert detect.gfx_drivers(gpus) == drivers


INTEL_RPL = (0x8086, 0xA7A0)
INTEL_ARC = (0x8086, 0x5693)
AMD_APU = (0x1002, 0x1681)
AMD_NAVI = (0x1002, 0x73FF)
NV_RTX = (0x10DE, 0x2520)
NV_PASCAL = (0x10DE, 0x1C8D)


@pytest.mark.parametrize(
	('gpus', 'kept'),
	[
		({INTEL_RPL, NV_RTX}, {GfxPackage.VulkanIntel, GfxPackage.NvidiaOpen}),
		({INTEL_RPL, NV_PASCAL}, {GfxPackage.VulkanIntel, GfxPackage.VulkanNouveau}),
		({AMD_APU, NV_RTX}, {GfxPackage.VulkanRadeon, GfxPackage.NvidiaOpen}),
	],
)
def test_hybrid_ticks_both_presets(gpus: set[tuple[int, int]], kept: set[GfxPackage]) -> None:
	# what Custom must hold: every package of either GPU's preset, once
	packages = detect.gfx_packages(gpus)
	presets = [set(GFX_PACKAGES[d]) for d in detect.gfx_drivers(gpus)]

	assert detect.is_hybrid(gpus, portable=True)
	assert set(packages) == set.union(*presets)
	assert kept <= set(packages)
	assert len(packages) == len(set(packages))


@pytest.mark.parametrize(
	('gpus', 'portable'),
	[
		# a desktop's iGPU beside the card is not a hybrid to drive
		({INTEL_RPL, NV_RTX}, False),
		# same vendor twice: one preset covers both
		({AMD_APU, AMD_NAVI}, True),
		({INTEL_RPL, INTEL_ARC}, True),
		({INTEL_RPL}, True),
	],
)
def test_not_hybrid(gpus: set[tuple[int, int]], portable: bool) -> None:
	assert not detect.is_hybrid(gpus, portable)


def test_vendors_skip_unknown_display_class() -> None:
	# ASPEED BMC on a server board is display class too
	assert detect.gpu_vendors({(0x1A03, 0x2000), (0x8086, 0xA7A0)}) == ['intel']


def _driver_buses(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, buses: dict[str, dict[str, str | None]]) -> None:
	# name -> module when bound, None for an unbound device with only a MODALIAS
	root = tmp_path / 'bus'
	modules = tmp_path / 'modules'
	modules.mkdir()
	for bus, devices in buses.items():
		for name, module in devices.items():
			dev = root / bus / 'devices' / name
			dev.mkdir(parents=True)
			if module is None:
				(dev / 'uevent').write_text(f'DRIVER=\nMODALIAS=pci:v0000{name}d0\n')
				continue
			(modules / module).mkdir(exist_ok=True)
			(dev / 'driver').mkdir()
			(dev / 'driver' / 'module').symlink_to(modules / module)
	monkeypatch.setattr(detect, '_SYS_BUS', root)


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

	monkeypatch.setattr(detect, '_run_splitlines', fake_run)
	return calls


def _declared() -> dict[str, set[str]]:
	return detect.declared_firmware(RELEASE, detect.device_modules(RELEASE))


def test_modprobe_resolves_against_target_release(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
	# after an upgrade without reboot the running kernel's modules are gone
	_driver_buses(monkeypatch, tmp_path, {'pci': {'0000:00:03.0': None}})
	calls = _stub_run(monkeypatch)

	detect.device_modules(RELEASE)

	assert [c for c in calls if c[0] == 'modprobe'] == [['modprobe', '-S', RELEASE, '-R', 'pci:v00000000:00:03.0d0']]


def test_modinfo_asks_the_module_not_the_driver(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
	# i801_smbus is the driver directory, i2c_i801 the module modinfo answers to
	_driver_buses(monkeypatch, tmp_path, {'pci': {'0000:00:1f.4': 'i2c_i801'}})
	calls = _stub_run(monkeypatch)

	assert _declared() == {}
	assert {c[-1] for c in calls if c[0] == 'modinfo'} == {'i2c_i801'}


def test_wrapper_reaches_its_parent(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
	# CS35L41 sits on the ACPI bus, binds through the _i2c wrapper, and the
	# wrapper declares no firmware: the blobs are on the parent it depends on
	_driver_buses(monkeypatch, tmp_path, {'acpi': {'CSC3551:00': 'snd_hda_scodec_cs35l41_i2c'}})
	_stub_run(
		monkeypatch,
		firmware={
			'snd_hda_scodec_cs35l41': ['cirrus/cs35l41-*.bin'],
			'snd_soc_cs35l41_lib': ['cirrus/lib-only.bin'],
		},
		depends={'snd_hda_scodec_cs35l41_i2c': 'snd-hda-scodec-cs35l41,snd-soc-cs35l41-lib'},
	)

	assert _declared() == {'snd_hda_scodec_cs35l41': {'cirrus/cs35l41-*.bin'}}


def test_btusb_skips_the_other_vendors_helpers(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
	# btusb links every vendor helper and picks one at probe; none of them
	# is a parent it wraps, so their family-wide blob lists stay out
	_driver_buses(monkeypatch, tmp_path, {'usb': {'3-10:1.0': 'btusb'}})
	_stub_run(
		monkeypatch,
		firmware={'btmtk': ['mediatek/mt7668pr2h.bin'], 'btrtl': ['rtl_bt/rtl8822b_fw.bin']},
		depends={'btusb': 'bluetooth,btmtk,btintel,btbcm,btrtl'},
	)

	assert _declared() == {}


@pytest.mark.parametrize(
	('declared', 'index', 'splits'),
	[
		# the 0x17cb case: ath11k blobs ship in -atheros, not -qcom
		(
			{'ath11k_pci': {'ath11k/WCN6855/hw2.0/*'}},
			{'ath11k/WCN6855/hw2.0/board-2.bin': 'linux-firmware-atheros'},
			{FirmwareVendor.ATHEROS: ['ath11k_pci']},
		),
		# ti_usb_3410_5052 mixes flat mts_* (-other) and flat ti_* (-ti)
		(
			{'ti_usb_3410_5052': {'mts_edge.fw', 'ti_3410.fw'}},
			{'mts_edge.fw': 'linux-firmware-other', 'ti_3410.fw': 'linux-firmware-ti'},
			{FirmwareVendor.OTHER: ['ti_usb_3410_5052'], FirmwareVendor.TI: ['ti_usb_3410_5052']},
		),
		# two modules on one split list both, sorted
		(
			{'iwlwifi': {'iwlwifi-cc-a0-77.ucode'}, 'i915': {'i915/tgl_dmc.bin'}},
			{'iwlwifi-cc-a0-77.ucode': 'linux-firmware-intel', 'i915/tgl_dmc.bin': 'linux-firmware-intel'},
			{FirmwareVendor.INTEL: ['i915', 'iwlwifi']},
		),
		# owners outside the enum drop: microcode, regdb, an unknown split
		(
			{'k10temp': {'amd-ucode/microcode_amd.bin', 'regulatory.db', 'new/blob.bin'}},
			{
				'amd-ucode/microcode_amd.bin': 'amd-ucode',
				'regulatory.db': 'wireless-regdb',
				'new/blob.bin': 'linux-firmware-new',
			},
			{},
		),
	],
)
def test_splits_from_ownership(
	declared: dict[str, set[str]],
	index: dict[str, str],
	splits: dict[FirmwareVendor, list[str]],
) -> None:
	assert detect.firmware_splits(declared, index) == splits


def test_optdeps_are_the_splits_full_leaves_out() -> None:
	splits = {FirmwareVendor.INTEL: ['iwlwifi'], FirmwareVendor.MARVELL: ['mwifiex_pcie'], FirmwareVendor.QLOGIC: ['qla2xxx']}
	assert detect.firmware_optdeps(splits) == [FirmwareVendor.MARVELL, FirmwareVendor.QLOGIC]


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
	monkeypatch.setattr(_FakeDB, 'listing', [('linux-firmware-ti', 'usr/lib/firmware/ti_3410.fw.zst'), ('bash', 'usr/bin/bash')])
	monkeypatch.setattr(detect, 'TmpDB', _FakeDB)

	assert detect.firmware_index() == {'ti_3410.fw': 'linux-firmware-ti'}


def test_failed_sync_leaves_no_index(monkeypatch: pytest.MonkeyPatch) -> None:
	monkeypatch.setattr(_FakeDB, 'synced', False)
	monkeypatch.setattr(detect, 'TmpDB', _FakeDB)

	assert detect.firmware_index() == {}
