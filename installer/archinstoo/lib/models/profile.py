from enum import Enum, StrEnum, auto


class DisplayServer(Enum):
	X11 = 'x11'
	Wayland = 'wayland'

	def packages(self) -> list[str]:
		# Wayland compositors pull their own deps, X11 needs the server itself
		match self:
			case DisplayServer.X11:
				return ['xorg-server', 'xorg-xinit']
			case DisplayServer.Wayland:
				return []


class ProfileType(Enum):
	# top level default_profiles
	Server = 'server'
	Desktop = 'desktop'
	Xorg = 'xorg'
	Wayland = 'wayland'
	Minimal = 'minimal'
	Custom = 'custom'
	# detailed selection default_profiles
	ServerType = 'servertype'
	WindowMgr = 'window manager'
	DesktopEnv = 'desktop environment'
	# bar/launcher/notifications on a compositor it provisions the config
	# of: two would fight over that config, so a selection holds one
	Shell = 'shell'
	CustomType = 'customtype'

	# Custom are place-holders
	# wayland is hidden in menu
	# it is not used 'standalone' usually as
	# deps of a DE/WM, just a base class
	# 'profile.py' and 'wayland.py' are
	# hidden by /lib/profile/profiles_handler.py


class SeatAccess(StrEnum):
	# value is the package to install, label is the mechanism it provides.
	# polkit grants no seat access on its own: the real choice is
	# systemd-logind or seatd. Arch builds logind with polkit support, so
	# logind needs polkit at runtime for its permission checks (pacman only
	# lists it as an optdep of systemd, the requirement is functional).
	# https://github.com/archlinux/archinstall/issues/3467
	#
	# StrEnum so the saved string compares equal to the member: the menus
	# hand custom_settings['seat_access'] straight to set_default_by_value.
	seatd = 'seatd'
	logind = 'polkit'

	@property
	def label(self) -> str:
		return 'systemd-logind' if self is SeatAccess.logind else self.value


def seat_packages(pref: object) -> list[str]:
	# the saved value is the package; unset until the menu runs
	return [pref] if isinstance(pref, str) else []


def seat_services(pref: object) -> list[str]:
	# per the issue above, only seatd needs its service enabled. logind is
	# already up as part of systemd, and polkit is D-Bus activated with no
	# [Install] section, so enabling it exits 0 and does nothing.
	return [SeatAccess.seatd.value] if pref == SeatAccess.seatd.value else []


class GreeterType(Enum):
	Lightdm = 'lightdm-gtk-greeter'
	LightdmSlick = 'lightdm-slick-greeter'
	PlasmaLoginManager = 'plasma-login-manager'
	Sddm = 'sddm'
	Gdm = 'gdm'
	Ly = 'ly'
	Greetd = 'greetd'
	Tuigreet = 'tuigreet'
	Regreet = 'regreet'
	CosmicSession = 'cosmic-greeter'
	Noctalia = 'noctalia-greeter'
	NwgHello = 'nwg-hello'

	@property
	def packages(self) -> list[str]:
		match self:
			case GreeterType.Lightdm:
				return ['lightdm', 'lightdm-gtk-greeter']
			case GreeterType.LightdmSlick:
				return ['lightdm', 'lightdm-slick-greeter']
			case GreeterType.PlasmaLoginManager:
				return ['plasma-login-manager']
			case GreeterType.Sddm:
				return ['sddm']
			case GreeterType.Gdm:
				return ['gdm']
			case GreeterType.Ly:
				return ['ly']
			case GreeterType.Greetd:
				return ['greetd']
			case GreeterType.Tuigreet:
				# tuigreet draws on the tty itself, no
				# compositor to host it
				return ['greetd', 'greetd-tuigreet']
			case GreeterType.Regreet:
				# regreet (GUI) runs inside the cage kiosk compositor
				return ['greetd', 'greetd-regreet', 'cage']
			case GreeterType.CosmicSession:
				return ['cosmic-greeter']
			case GreeterType.Noctalia:
				# ships its own wlroots compositor
				return ['greetd', 'noctalia-greeter']
			case GreeterType.NwgHello:
				# gtk-layer-shell greeter, hosted by sway
				return ['greetd', 'nwg-hello', 'sway']

	@property
	def services(self) -> list[str]:
		match self:
			case GreeterType.Lightdm | GreeterType.LightdmSlick:
				return ['lightdm']
			case GreeterType.PlasmaLoginManager:
				return ['plasmalogin']
			case GreeterType.Ly:
				return ['ly@tty1']
			case (
				GreeterType.Tuigreet
				| GreeterType.Regreet
				| GreeterType.Noctalia
				| GreeterType.NwgHello
			):
				return ['greetd']
			case _:
				return [self.value]

	@property
	def disabled_services(self) -> list[str]:
		# these take over vt1, so the getty that owns it has to go
		match self:
			case (
				GreeterType.Ly
				| GreeterType.Tuigreet
				| GreeterType.Regreet
				| GreeterType.Noctalia
				| GreeterType.NwgHello
			):
				return ['getty@tty1']
			case _:
				return []


class SelectResult(Enum):
	NewSelection = auto()
	SameSelection = auto()
	ResetCurrent = auto()
