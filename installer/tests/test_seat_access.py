# The seat_access choice is one string used three ways: package, service,
# menu default. These lock each use across every profile that offers it.
# https://github.com/archlinux/archinstall/issues/3467

from typing import TYPE_CHECKING

import pytest

from archinstoo.default_profiles.desktops import SeatAccess, seat_services
from archinstoo.default_profiles.desktops.dms import DmsProfile
from archinstoo.default_profiles.desktops.hyprland import HyprlandProfile
from archinstoo.default_profiles.desktops.labwc import LabwcProfile
from archinstoo.default_profiles.desktops.niri import NiriProfile
from archinstoo.default_profiles.desktops.noctalia import NoctaliaProfile
from archinstoo.default_profiles.desktops.river import RiverProfile
from archinstoo.default_profiles.desktops.sway import SwayProfile
from archinstoo.lib.tui.menu_item import MenuItem, MenuItemGroup

if TYPE_CHECKING:
	from archinstoo.default_profiles.wayland import WaylandProfile

SEAT_PROFILES: list[type[WaylandProfile]] = [
	DmsProfile,
	HyprlandProfile,
	LabwcProfile,
	NiriProfile,
	NoctaliaProfile,
	RiverProfile,
	SwayProfile,
]


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
def test_saved_choice_preselects_menu_item(seat: SeatAccess) -> None:
	# custom_settings stores the plain string, the menu items carry the member
	items = [MenuItem(s.label, value=s) for s in SeatAccess]
	group = MenuItemGroup(items, sort_items=True)

	group.set_default_by_value(seat.value)

	assert group.default_item is not None
	assert group.default_item.value is seat


def test_labels_name_the_mechanism() -> None:
	assert SeatAccess.logind.label == 'systemd-logind'
	assert SeatAccess.seatd.label == 'seatd'
	# the saved-config and nvchecker token stays the package name
	assert SeatAccess('polkit') is SeatAccess.logind
