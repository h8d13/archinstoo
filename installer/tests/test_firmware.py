from typing import TYPE_CHECKING

import pytest

from archinstoo.lib.hardware import _SysInfo
from archinstoo.lib.models.firmware import FirmwareConfiguration, FirmwareType, FirmwareVendor

if TYPE_CHECKING:
	from pathlib import Path

# Taken unconditionally: no bus ID reaches either one
BASELINE = {'CIRRUS', 'OTHER'}


def _fake_bus(root: Path, attr: str, ids: list[str]) -> Path:
	# Mirrors sysfs: one directory per device holding a vendor-ID attribute
	root.mkdir(parents=True, exist_ok=True)
	for idx, vendor_id in enumerate(ids):
		dev = root / f'dev{idx}'
		dev.mkdir()
		(dev / attr).write_text(vendor_id + '\n')
	return root


def _detect(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, pci: list[str], usb: list[str]) -> set[str]:
	monkeypatch.setattr('archinstoo.lib.hardware._PCI_BUS', _fake_bus(tmp_path / 'pci', 'vendor', pci))
	monkeypatch.setattr('archinstoo.lib.hardware._USB_BUS', _fake_bus(tmp_path / 'usb', 'idVendor', usb))

	return set(_SysInfo().firmware_vendors)


@pytest.mark.parametrize(
	('pci', 'usb', 'expected'),
	[
		# regression: 0x17cb blobs ship in -atheros, not -qcom
		(['0x17cb'], [], {'ATHEROS'}),
		(['0x168c'], [], {'ATHEROS'}),
		(['0x1814'], [], {'MEDIATEK'}),
		(['0x14c3'], [], {'MEDIATEK'}),
		(['0x1002'], [], {'AMDGPU', 'RADEON'}),
		(['0x10de'], [], {'NVIDIA'}),
		# 0cf3 is USB-only, absent from pci.ids
		([], ['0cf3'], {'ATHEROS'}),
		(['0cf3'], [], set()),
		([], ['8087'], {'INTEL'}),
		([], ['0bda'], {'REALTEK'}),
		# root hub, Samsung NVMe, ASMedia: nothing to pull
		([], ['1d6b'], set()),
		(['0x144d', '0x1b21'], [], set()),
	],
)
def test_firmware_vendor_detection(
	monkeypatch: pytest.MonkeyPatch,
	tmp_path: Path,
	pci: list[str],
	usb: list[str],
	expected: set[str],
) -> None:
	assert _detect(monkeypatch, tmp_path, pci, usb) == BASELINE | expected


def test_firmware_baseline_without_any_device(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
	assert _detect(monkeypatch, tmp_path, [], []) == BASELINE


def test_firmware_skips_devices_without_vendor_attr(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
	# USB interface nodes (1-1:1.0) carry no idVendor and must not abort the sweep
	usb = _fake_bus(tmp_path / 'usb', 'idVendor', ['8087'])
	(usb / '1-1:1.0').mkdir()

	monkeypatch.setattr('archinstoo.lib.hardware._PCI_BUS', tmp_path / 'absent')
	monkeypatch.setattr('archinstoo.lib.hardware._USB_BUS', usb)

	assert set(_SysInfo().firmware_vendors) == BASELINE | {'INTEL'}


def test_detected_names_resolve_to_vendors(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
	# The scan emits bare enum names, so every one has to resolve on the caller's side
	names = _detect(monkeypatch, tmp_path, ['0x1002', '0x8086', '0x17cb'], ['0bda'])

	assert [FirmwareVendor[name] for name in names]


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


@pytest.mark.parametrize(
	('config', 'expected'),
	[
		(FirmwareConfiguration(), ['linux-firmware']),
		(FirmwareConfiguration(firmware_type=FirmwareType.MINIMAL), []),
		(
			FirmwareConfiguration(firmware_type=FirmwareType.VENDOR, vendors=[FirmwareVendor.INTEL]),
			['linux-firmware-intel'],
		),
	],
)
def test_firmware_packages(config: FirmwareConfiguration, expected: list[str]) -> None:
	assert config.packages() == expected
