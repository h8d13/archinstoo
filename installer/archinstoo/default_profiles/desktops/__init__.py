from enum import Enum


class SeatAccess(Enum):
	# value is the package to install, label is the mechanism it provides.
	# polkit grants no seat access on its own: the real choice is
	# systemd-logind (which hard-depends on polkit on Arch) or seatd.
	# https://github.com/archlinux/archinstall/issues/3467
	seatd = 'seatd'
	logind = 'polkit'

	@property
	def label(self) -> str:
		return 'systemd-logind' if self is SeatAccess.logind else self.value


def seat_services(pref: object) -> list[str]:
	# per the issue above, only seatd needs its service enabled. logind is
	# already up as part of systemd, and polkit is D-Bus activated with no
	# [Install] section, so enabling it exits 0 and does nothing.
	return [SeatAccess.seatd.value] if pref == SeatAccess.seatd.value else []
