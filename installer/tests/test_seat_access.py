# The seat_access choice is one string used three ways: package, service,
# menu default. These lock each use across every profile that offers it.
# https://github.com/archlinux/archinstall/issues/3467

from typing import TYPE_CHECKING

import pytest

from archinstoo.default_profiles import desktops
from archinstoo.default_profiles.desktops import select_seat_access
from archinstoo.default_profiles.desktops.dms import DmsProfile
from archinstoo.default_profiles.desktops.hyprland import HyprlandProfile
from archinstoo.default_profiles.desktops.labwc import LabwcProfile
from archinstoo.default_profiles.desktops.niri import NiriProfile
from archinstoo.default_profiles.desktops.noctalia import NoctaliaProfile
from archinstoo.default_profiles.desktops.river import RiverProfile
from archinstoo.default_profiles.desktops.sway import SwayProfile
from archinstoo.lib.profile.base import SeatAccess, seat_services
from archinstoo.lib.tui.result import Result, ResultType

if TYPE_CHECKING:
	from archinstoo.default_profiles.wayland import WaylandProfile
	from archinstoo.lib.tui.menu_item import MenuItemGroup

SEAT_PROFILES: list[type[WaylandProfile]] = [
	DmsProfile,
	HyprlandProfile,
	LabwcProfile,
	NiriProfile,
	NoctaliaProfile,
	RiverProfile,
	SwayProfile,
]


class FakeMenu:
	# stands in for SelectMenu: keeps every group it was built with, in order,
	# and accepts the preselected entry as Enter does, without a terminal
	groups: list[MenuItemGroup]

	def __init__(self, group: MenuItemGroup, **_: object) -> None:
		self.group = group
		FakeMenu.groups.append(group)

	@classmethod
	def __class_getitem__(cls, _: object) -> type[FakeMenu]:
		return cls

	def run(self) -> Result[object]:
		return Result(ResultType.Selection, self.group.default_item)


@pytest.fixture
def fake_menu(monkeypatch: pytest.MonkeyPatch) -> type[FakeMenu]:
	monkeypatch.setattr(desktops, 'SelectMenu', FakeMenu)
	monkeypatch.setattr(FakeMenu, 'groups', [], raising=False)
	return FakeMenu


@pytest.mark.parametrize('profile_cls', SEAT_PROFILES)
@pytest.mark.parametrize('seat', list(SeatAccess))
def test_chosen_seat_package_is_installed(profile_cls: type[WaylandProfile], seat: SeatAccess) -> None:
	# enabling seatd.service without the seatd package exits 1 and aborts the
	# install; the logind path needs the polkit package for the same reason
	profile = profile_cls()
	profile.custom_settings['seat_access'] = seat.value

	assert seat.value in profile.packages


@pytest.mark.parametrize('profile_cls', SEAT_PROFILES)
def test_no_seat_package_when_unset(profile_cls: type[WaylandProfile]) -> None:
	packages = profile_cls().packages

	assert not any(s.value in packages for s in SeatAccess)


def test_only_seatd_ships_a_unit() -> None:
	# polkit.service has no [Install] and is D-Bus activated, enable is a no-op
	assert seat_services(SeatAccess.seatd.value) == ['seatd']
	assert seat_services(SeatAccess.logind.value) == []
	assert seat_services(None) == []


@pytest.mark.parametrize('seat', list(SeatAccess))
def test_saved_choice_preselects_and_saves_plain_string(seat: SeatAccess, fake_menu: type[FakeMenu]) -> None:
	# custom_settings stores the plain string, the menu items carry the member
	picked = select_seat_access('Sway', seat.value)

	[group] = fake_menu.groups
	assert group.default_item is not None
	assert group.default_item.value is seat
	# a StrEnum member would serialize fine but compare as a different type
	assert type(picked) is str
	assert picked == seat.value


def test_labels_name_the_mechanism() -> None:
	assert SeatAccess.logind.label == 'systemd-logind'
	assert SeatAccess.seatd.label == 'seatd'
	# the saved-config and nvchecker token stays the package name
	assert SeatAccess('polkit') is SeatAccess.logind
