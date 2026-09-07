# The custom graphics driver: a hand-picked package list in place of a preset.
# Covers the one derived step (the nvidia-open dkms swap) on both the install
# path and the count/size mirror, the config round trip that drops unknowns,
# and the host GPU probe that pre-ticks the picker.
from types import SimpleNamespace
from typing import TYPE_CHECKING

import pytest

from archinstoo.lib import hardware
from archinstoo.lib.hardware import (
	GFX_CUSTOM_CHOICES,
	GfxDriver,
	GfxPackage,
	detected_gfx_drivers,
	detected_gfx_packages,
	dkms_packages,
	hybrid_gfx_packages,
)
from archinstoo.lib.profile.base import DisplayServer
from archinstoo.lib.profile.config import ProfileConfiguration
from archinstoo.lib.profile.profiles_handler import ProfileHandler
from archinstoo.scripts import _resolve

if TYPE_CHECKING:
	from pathlib import Path

HYBRID = [GfxPackage.NvidiaOpen, GfxPackage.VulkanIntel, GfxPackage.Mesa]


def test_custom_choices_leave_out_derived_packages() -> None:
	derived = {GfxPackage.Dkms, GfxPackage.NvidiaOpenDkms, GfxPackage.XorgServer, GfxPackage.XorgXinit}
	assert not derived & set(GFX_CUSTOM_CHOICES)
	assert set(GFX_CUSTOM_CHOICES) | derived == set(GfxPackage)


@pytest.mark.parametrize(
	('kernels', 'expected'),
	[
		(['linux'], HYBRID),
		(None, HYBRID),
		(['linux-zen'], [GfxPackage.NvidiaOpenDkms, GfxPackage.VulkanIntel, GfxPackage.Mesa, GfxPackage.Dkms]),
	],
)
def test_dkms_swap_only_touches_nvidia_open(kernels: list[str] | None, expected: list[GfxPackage]) -> None:
	assert dkms_packages(HYBRID, kernels) == expected
	# nothing to swap: the list comes back as-is, not with a stray dkms
	assert dkms_packages([GfxPackage.Mesa], ['linux-zen']) == [GfxPackage.Mesa]


def test_presets_still_resolve_through_the_shared_swap() -> None:
	assert GfxDriver.NvidiaOpenKernel.gfx_packages(['linux-lts']) == [
		GfxPackage.NvidiaOpenDkms,
		GfxPackage.LibvaNvidiaDriver,
		GfxPackage.Dkms,
	]
	assert GfxDriver.Custom.gfx_packages(['linux-lts']) == []


def test_resolve_mirrors_the_install_path() -> None:
	custom = [p.value for p in HYBRID]
	assert _resolve._gfx_packages('custom', custom, ['linux'], []) == set(custom)
	assert _resolve._gfx_packages('custom', custom, ['linux-zen'], []) == {
		'nvidia-open-dkms',
		'dkms',
		'linux-zen-headers',
		'vulkan-intel',
		'mesa',
	}
	# a name outside the pool never reaches pacman, and dkms cannot be forced by hand
	assert _resolve._gfx_packages('custom', ['mesa', 'nvidia-390xx', 'dkms'], ['linux'], []) == {'mesa'}


def test_config_round_trip_drops_unknown_names() -> None:
	parsed = ProfileConfiguration.parse_arg(
		{'profiles': [], 'gfx_driver': 'custom', 'gfx_packages': ['mesa', 'vulkan-intel', 'not-a-package'], 'greeter': None}
	)
	assert parsed.gfx_driver is GfxDriver.Custom
	assert parsed.gfx_packages == [GfxPackage.Mesa, GfxPackage.VulkanIntel]
	assert parsed.json()['gfx_packages'] == ['mesa', 'vulkan-intel']

	# a preset driver carries no list, an absent key parses as none
	plain = ProfileConfiguration.parse_arg({'profiles': [], 'gfx_driver': 'mesa-open-source', 'greeter': None})  # type: ignore[typeddict-item]
	assert plain.gfx_packages == []


# -- host GPU detection feeding the picker --


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
	bus = _fake_gpus(
		tmp_path,
		[
			('0x030000', '0x10de', '0x2208'),  # GA102, VGA
			('0x030200', '0x8086', '0xa7a0'),  # Raptor Lake iGPU, 3D
			('0x0c0330', '0x8086', '0x7ae0'),  # xHCI, not a GPU
		],
	)
	monkeypatch.setattr(hardware, '_PCI_BUS', bus)
	monkeypatch.setattr(hardware, '_sys_info', hardware._SysInfo())
	assert hardware.SysInfo.gpu_ids() == {(0x10DE, 0x2208), (0x8086, 0xA7A0)}


def test_gpu_ids_empty_without_a_bus(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
	monkeypatch.setattr(hardware, '_PCI_BUS', tmp_path / 'absent')
	monkeypatch.setattr(hardware, '_sys_info', hardware._SysInfo())
	assert hardware.SysInfo.gpu_ids() == set()


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
def test_detected_drivers_per_gpu(gpus: set[tuple[int, int]], drivers: list[GfxDriver]) -> None:
	assert detected_gfx_drivers(gpus) == drivers


def test_detected_packages_union_both_halves() -> None:
	packages = detected_gfx_packages({(0x8086, 0xA7A0), (0x10DE, 0x2208)})
	assert GfxPackage.VulkanIntel in packages
	assert GfxPackage.NvidiaOpen in packages
	# shared packages appear once
	assert packages.count(GfxPackage.Mesa) == 1
	assert set(packages) <= set(GFX_CUSTOM_CHOICES)


# -- hybrid extras: PRIME glue on top of the per-GPU sets --


@pytest.mark.parametrize(
	('drivers', 'expected'),
	[
		([GfxDriver.IntelOpenSource], []),
		([GfxDriver.NvidiaOpenKernel], []),
		([GfxDriver.IntelOpenSource, GfxDriver.AmdOpenSource], [GfxPackage.SwitcherooControl, GfxPackage.VulkanMesaLayers]),
		(
			[GfxDriver.AmdOpenSource, GfxDriver.NvidiaOpenKernel],
			[GfxPackage.SwitcherooControl, GfxPackage.VulkanMesaLayers, GfxPackage.NvidiaPrime],
		),
		# nouveau is a mesa driver: DRI_PRIME, not prime-run
		([GfxDriver.IntelOpenSource, GfxDriver.NvidiaOpenSource], [GfxPackage.SwitcherooControl, GfxPackage.VulkanMesaLayers]),
	],
)
def test_hybrid_extras_need_two_gpus(drivers: list[GfxDriver], expected: list[GfxPackage]) -> None:
	assert hybrid_gfx_packages(drivers) == expected


def test_detected_packages_carry_the_hybrid_extras() -> None:
	single = detected_gfx_packages({(0x10DE, 0x2208)})
	assert GfxPackage.NvidiaPrime not in single
	assert GfxPackage.SwitcherooControl not in single

	hybrid = detected_gfx_packages({(0x8086, 0xA7A0), (0x10DE, 0x2208)})
	assert hybrid[-3:] == [GfxPackage.SwitcherooControl, GfxPackage.VulkanMesaLayers, GfxPackage.NvidiaPrime]
	assert set(hybrid) <= set(GFX_CUSTOM_CHOICES)


def test_install_enables_the_service_a_pick_owns(monkeypatch: pytest.MonkeyPatch) -> None:
	installed: list[str] = []
	enabled: list[str] = []
	session = SimpleNamespace(kernels=['linux'], add_additional_packages=installed.extend, enable_service=enabled.extend)

	handler = ProfileHandler()
	handler.install_gfx_driver(session, GfxDriver.Custom, {DisplayServer.Wayland}, [GfxPackage.Mesa, GfxPackage.SwitcherooControl])  # type: ignore[arg-type]
	assert installed == ['mesa', 'switcheroo-control']
	assert enabled == ['switcheroo-control']

	# no switcheroo pick, no unit; a preset behaves the same as before
	installed.clear()
	enabled.clear()
	handler.install_gfx_driver(session, GfxDriver.IntelOpenSource, {DisplayServer.Wayland})  # type: ignore[arg-type]
	assert installed == [p.value for p in GfxDriver.IntelOpenSource.gfx_packages(['linux'])]
	assert enabled == []
