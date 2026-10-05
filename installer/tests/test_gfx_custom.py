# The custom graphics driver: a hand-picked package list in place of a preset.
# Covers the one derived step (the nvidia-open dkms swap) on both the install
# path and the count mirror, the config round trip that drops unknowns,
# and the host GPU probe that pre-ticks the picker.
from types import SimpleNamespace
from typing import TYPE_CHECKING

import pytest

from archinstoo.lib import hardware
from archinstoo.lib.args import ArchConfig
from archinstoo.lib.hardware import (
	GFX_CUSTOM_CHOICES,
	GFX_PACKAGES,
	GfxDriver,
	GfxPackage,
	detected_gfx_drivers,
	detected_gfx_packages,
	dkms_packages,
)
from archinstoo.lib.profile.base import DisplayServer
from archinstoo.lib.profile.config import ProfileConfiguration
from archinstoo.lib.profile.profiles_handler import ProfileHandler
from archinstoo.scripts import _resolve

if TYPE_CHECKING:
	from pathlib import Path

HYBRID = [GfxPackage.NvidiaOpen, GfxPackage.VulkanIntel, GfxPackage.Mesa]


def test_custom_choices_leave_out_derived_packages() -> None:
	derived = {GfxPackage.Dkms, GfxPackage.NvidiaOpenDkms}
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
	assert _resolve._gfx_packages('custom', custom, ['linux']) == set(custom)
	assert _resolve._gfx_packages('custom', custom, ['linux-zen']) == {
		'nvidia-open-dkms',
		'dkms',
		'linux-zen-headers',
		'vulkan-intel',
		'mesa',
	}
	# a name outside the pool never reaches pacman, and dkms cannot be forced by hand
	assert _resolve._gfx_packages('custom', ['mesa', 'nvidia-390xx', 'dkms'], ['linux']) == {'mesa'}


def test_config_round_trip_drops_unknown_names() -> None:
	parsed = ArchConfig.from_config({'gfx_driver': 'custom', 'gfx_packages': ['mesa', 'vulkan-intel', 'not-a-package']})
	assert parsed.gfx_driver is GfxDriver.Custom
	assert parsed.gfx_packages == [GfxPackage.Mesa, GfxPackage.VulkanIntel]
	assert parsed.safe_json()['gfx_packages'] == ['mesa', 'vulkan-intel']

	# a preset driver carries no list, an absent key parses as none
	plain = ArchConfig.from_config({'gfx_driver': 'mesa-open-source'})
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


def test_vendor_checks_read_gpu_ids(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
	# hybrid dGPUs often report as Display controller (0x0380)
	bus = _fake_gpus(
		tmp_path,
		[
			('0x030000', '0x8086', '0xa7a0'),  # Raptor Lake iGPU
			('0x038000', '0x1002', '0x73ff'),  # Navi 23 mobile, Display controller
			('0x060000', '0x1022', '0x14e8'),  # AMD host bridge, not a GPU
		],
	)
	monkeypatch.setattr(hardware, '_PCI_BUS', bus)
	monkeypatch.setattr(hardware, '_sys_info', hardware._SysInfo())

	assert hardware.SysInfo.has_intel_graphics()
	assert hardware.SysInfo.has_amd_graphics()
	assert not hardware.SysInfo.has_nvidia_graphics()


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


# -- mesa and hybrids: every GPU gets its vulkan driver, glue stays opt-in --

INTEL, AMD, TURING, ASPEED = (0x8086, 0xA7A0), (0x1002, 0x73FF), (0x10DE, 0x2520), (0x1A03, 0x2000)


def _host_gpus(monkeypatch: pytest.MonkeyPatch, gpus: set[tuple[int, int]], chassis: str = '10') -> None:
	info = hardware._SysInfo()
	info.__dict__.update(gpu_ids=gpus, is_portable=chassis in hardware._PORTABLE_CHASSIS)
	monkeypatch.setattr(hardware, '_sys_info', info)


@pytest.mark.parametrize(
	('gpus', 'vulkan'),
	[
		({INTEL}, {'vulkan-intel'}),
		({AMD}, {'vulkan-radeon'}),
		# nvidia under mesa runs nouveau, NVK is its vulkan
		({TURING}, {'vulkan-nouveau'}),
		({INTEL, AMD}, {'vulkan-intel', 'vulkan-radeon'}),
		({AMD, TURING}, {'vulkan-radeon', 'vulkan-nouveau'}),
		({ASPEED}, set()),
	],
)
def test_mesa_adds_vulkan_for_every_gpu(monkeypatch: pytest.MonkeyPatch, gpus: set[tuple[int, int]], vulkan: set[str]) -> None:
	_host_gpus(monkeypatch, gpus)
	installed = {p.value for p in GfxDriver.MesaOpenSource.gfx_packages(['linux'])}
	counted = _resolve._gfx_packages('mesa-open-source', [], ['linux'])

	assert installed == counted == {'mesa', *vulkan}


def test_detected_packages_leave_the_glue_unticked() -> None:
	packages = detected_gfx_packages({INTEL, TURING})
	assert GfxPackage.VulkanMesaLayers not in packages
	assert set(packages) == set(GFX_PACKAGES[GfxDriver.IntelOpenSource]) | set(GFX_PACKAGES[GfxDriver.NvidiaOpenKernel])


@pytest.mark.parametrize(
	('gpus', 'chassis', 'hybrid'),
	[
		({INTEL, TURING}, '10', True),
		# same vendor twice: an AMD Advantage laptop
		({(0x1002, 0x1681), AMD}, '9', True),
		({INTEL}, '10', False),
		# a desktop keeping its iGPU beside the card, a server's BMC beside one
		({INTEL, TURING}, '3', False),
		({ASPEED, TURING}, '10', False),
	],
)
def test_hybrid_needs_a_laptop_with_two_gpus(
	monkeypatch: pytest.MonkeyPatch,
	gpus: set[tuple[int, int]],
	chassis: str,
	hybrid: bool,
) -> None:
	_host_gpus(monkeypatch, gpus, chassis)
	assert hardware.SysInfo.has_hybrid_graphics() is hybrid


def test_custom_install_takes_the_picks_as_given() -> None:
	installed: list[str] = []
	session = SimpleNamespace(kernels=['linux'], add_additional_packages=installed.extend)

	handler = ProfileHandler()
	handler.install_gfx_driver(session, GfxDriver.Custom, [GfxPackage.Mesa, GfxPackage.VulkanMesaLayers])  # type: ignore[arg-type]
	assert installed == ['mesa', 'vulkan-mesa-layers']


def test_driver_installs_only_its_own_packages() -> None:
	# a headless box running CUDA picks a driver and never selects a profile:
	# no display server packages ride along with the driver
	installed: list[str] = []
	session = SimpleNamespace(kernels=['linux'], add_additional_packages=installed.extend)

	ProfileHandler().install_gfx_driver(session, GfxDriver.IntelOpenSource)  # type: ignore[arg-type]

	assert installed == [p.value for p in GfxDriver.IntelOpenSource.gfx_packages(['linux'])]


@pytest.mark.parametrize(('name', 'server'), [('xorg', DisplayServer.X11), ('sway', DisplayServer.Wayland)])
def test_profile_install_adds_its_display_server(name: str, server: DisplayServer) -> None:
	installed: list[str] = []
	session = SimpleNamespace(add_additional_packages=installed.extend)

	handler = ProfileHandler()
	profile = next(p for p in handler.profiles if p.name == name)
	assert server in profile.display_servers()
	handler.install_profile_config(session, ProfileConfiguration(profiles=[profile]), None)  # type: ignore[arg-type]

	assert set(server.packages()) <= set(installed)
