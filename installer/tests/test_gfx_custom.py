# The custom graphics driver: a hand-picked package list in place of a preset.
# Covers the one derived step (the nvidia-open dkms swap) on both the install
# path and the count mirror, and the config round trip that drops unknowns.
from types import SimpleNamespace

import pytest

from archinstoo.lib.args import ArchConfig
from archinstoo.lib.hardware import (
	GFX_CUSTOM_CHOICES,
	GfxDriver,
	GfxPackage,
	dkms_packages,
	gfx_custom_choices,
)
from archinstoo.lib.profile.base import DisplayServer
from archinstoo.lib.profile.config import ProfileConfiguration
from archinstoo.lib.profile.profiles_handler import ProfileHandler
from archinstoo.scripts import _resolve

HYBRID = [GfxPackage.NvidiaOpen, GfxPackage.VulkanIntel, GfxPackage.Mesa]


def test_custom_choices_leave_out_derived_packages() -> None:
	derived = {GfxPackage.Dkms, GfxPackage.NvidiaOpenDkms}
	assert not derived & set(GFX_CUSTOM_CHOICES)
	assert set(GFX_CUSTOM_CHOICES) | derived == set(GfxPackage)


def test_custom_choices_per_arch() -> None:
	x86 = set(gfx_custom_choices('x86_64'))
	arm = set(gfx_custom_choices('aarch64'))

	# aarch64: mesa and every vulkan driver, none of the x86 vendor stacks
	assert arm == {GfxPackage.Mesa} | {p for p in GfxPackage if p.value.startswith('vulkan-')}
	assert {GfxPackage.VulkanPanfrost, GfxPackage.VulkanFreedreno} <= arm - x86
	assert GfxPackage.NvidiaOpen in x86 - arm
	# both are slices of the pool the count mirror validates against
	assert x86 | arm == set(GFX_CUSTOM_CHOICES)


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


@pytest.mark.parametrize('driver', [d for d in GfxDriver if d is not GfxDriver.Custom])
@pytest.mark.parametrize('kernels', [['linux'], ['linux-zen']])
def test_presets_match_the_count_mirror(driver: GfxDriver, kernels: list[str]) -> None:
	# no host input: the install set and the counted set are the same table
	installed = {p.value for p in driver.gfx_packages(kernels)}
	if GfxPackage.NvidiaOpenDkms in driver.gfx_packages(kernels):
		installed |= {f'{k}-headers' for k in kernels}

	assert _resolve._gfx_packages(driver.value, [], kernels) == installed


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
