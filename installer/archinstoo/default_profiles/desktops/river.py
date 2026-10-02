import shutil
from typing import TYPE_CHECKING, override

from archinstoo.default_profiles.desktops import select_seat_access
from archinstoo.default_profiles.wayland import WaylandProfile
from archinstoo.lib.profile.base import ProfileType, seat_packages, seat_services

if TYPE_CHECKING:
	from archinstoo.lib.installer import Installer
	from archinstoo.lib.models.users import User


class RiverProfile(WaylandProfile):
	needs_terminal = True

	def __init__(self) -> None:
		super().__init__('river', ProfileType.WindowMgr)

		self.custom_settings = {'seat_access': None}

	@property
	@override
	def packages(self) -> list[str]:
		# `river` in extra is the 0.4 rewrite: compositor only, the window
		# manager is a separate client and none is packaged. river-classic
		# is the 0.3 line with riverctl/rivertile, the one that runs standalone
		return [
			'xdg-desktop-portal-wlr',
			'river-classic',
			'foot',
			# the shipped init binds the media keys to these three; eject is
			# util-linux. nothing else in it spawns a program
			'pamixer',
			'playerctl',
			'brightnessctl',
			*seat_packages(self.custom_settings.get('seat_access')),
		]

	@property
	@override
	def services(self) -> list[str]:
		return seat_services(self.custom_settings.get('seat_access'))

	@override
	def provision(self, install_session: Installer, users: list[User]) -> None:
		super().provision(install_session, users)

		# river reads ~/.config/river/init and nothing else (no /etc fallback):
		# no init means no bindings and no layout, a black screen
		shipped = install_session.target / 'usr/share/river-classic/example/init'

		for user in users:
			init = install_session.target / 'home' / user.username / '.config/river/init'
			init.parent.mkdir(parents=True, exist_ok=True)
			shutil.copy(shipped, init)
			# river runs init as a program, a 0644 copy is silently skipped
			init.chmod(0o755)

			install_session.chown_tree(user.username, f'/home/{user.username}/.config')

	@override
	def do_on_select(self) -> None:
		self.custom_settings['seat_access'] = select_seat_access(
			'River',
			self.custom_settings.get('seat_access'),
		)
