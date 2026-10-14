# The custom graphics driver: a hand-picked package list in place of a preset,
# the per-arch presets, and the config round trip that drops unknowns.
from types import SimpleNamespace

import pytest

from archinstoo.lib.args import ArchConfig
from archinstoo.lib.models.graphics import GFX_PACKAGES, GfxDriver, GfxPackage, gfx_custom_choices, gfx_drivers
from archinstoo.lib.profile.base import DisplayServer
from archinstoo.lib.profile.config import ProfileConfiguration
from archinstoo.lib.profile.profiles_handler import ProfileHandler


def test_custom_choices_per_arch() -> None:
	x86 = set(gfx_custom_choices('x86_64'))
	arm = set(gfx_custom_choices('aarch64'))

	assert x86 == set(GfxPackage)
	assert {GfxPackage.IntelMediaDriver, GfxPackage.IntelVplGpuRt} <= x86 - arm


@pytest.mark.parametrize('arch', ['x86_64', 'aarch64'])
def test_offered_presets_fit_the_arch(arch: str) -> None:
	hidden = set(GfxPackage) - set(gfx_custom_choices(arch))
	for driver in gfx_drivers(arch):
		assert hidden.isdisjoint(GFX_PACKAGES[driver]), driver


def test_every_preset_is_mesa_based() -> None:
	for driver, packages in GFX_PACKAGES.items():
		if driver is not GfxDriver.Custom:
			assert {GfxPackage.MesaDri, GfxPackage.MesaVulkan} <= set(packages), driver


def test_config_round_trip_drops_unknown_names() -> None:
	parsed = ArchConfig.from_config({'gfx_driver': 'custom', 'gfx_packages': ['mesa-dri-drivers', 'libva-intel-media-driver', 'not-a-package']})
	assert parsed.gfx_driver is GfxDriver.Custom
	assert parsed.gfx_packages == [GfxPackage.MesaDri, GfxPackage.IntelMediaDriver]
	assert parsed.safe_json()['gfx_packages'] == ['mesa-dri-drivers', 'libva-intel-media-driver']

	# a preset driver carries no list, an absent key parses as none
	plain = ArchConfig.from_config({'gfx_driver': 'mesa-open-source'})
	assert plain.gfx_packages == []


def test_custom_install_takes_the_picks_as_given() -> None:
	installed: list[str] = []
	session = SimpleNamespace(add_additional_packages=installed.extend)

	ProfileHandler().install_gfx_driver(session, GfxDriver.Custom, [GfxPackage.MesaDri, GfxPackage.XorgNouveau])  # type: ignore[arg-type]
	assert installed == ['mesa-dri-drivers', 'xorg-x11-drv-nouveau']


def test_driver_installs_only_its_own_packages() -> None:
	# a headless box picks a driver and never selects a profile: no display
	# server packages ride along with the driver
	installed: list[str] = []
	session = SimpleNamespace(add_additional_packages=installed.extend)

	ProfileHandler().install_gfx_driver(session, GfxDriver.IntelOpenSource)  # type: ignore[arg-type]

	assert installed == [p.value for p in GfxDriver.IntelOpenSource.gfx_packages()]


@pytest.mark.parametrize(('name', 'server'), [('xorg', DisplayServer.X11), ('sway', DisplayServer.Wayland)])
def test_profile_install_adds_its_display_server(name: str, server: DisplayServer) -> None:
	installed: list[str] = []
	session = SimpleNamespace(add_additional_packages=installed.extend)

	handler = ProfileHandler()
	profile = next(p for p in handler.profiles if p.name == name)
	assert server in profile.display_servers()
	handler.install_profile_config(session, ProfileConfiguration(profiles=[profile]), None)  # type: ignore[arg-type]

	assert set(server.packages()) <= set(installed)
