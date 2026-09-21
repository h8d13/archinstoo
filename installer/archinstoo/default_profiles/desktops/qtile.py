from typing import TYPE_CHECKING, override

from archinstoo.default_profiles.desktops import provision_terminal_config
from archinstoo.default_profiles.xorg import XorgProfile
from archinstoo.lib.profile.base import GreeterType, ProfileType

if TYPE_CHECKING:
	from archinstoo.lib.installer import Installer
	from archinstoo.lib.models.users import User


class QtileProfile(XorgProfile):
	needs_terminal = True

	def __init__(self) -> None:
		super().__init__('qtile', ProfileType.WindowMgr)

	@property
	@override
	def packages(self) -> list[str]:
		# ttf: bar renders as boxes without a scalable font
		# dbus-fast: optdep qtile warns about on every start
		# xwayland: the shipped "Qtile (Wayland)" session exits 1 without it
		return [
			'qtile',
			'ttf-liberation',
			'python-dbus-fast',
			'xorg-xwayland',
		]

	@override
	def provision(self, install_session: Installer, users: list[User]) -> None:
		# without ~/.config/qtile/config.py qtile runs the root-owned copy in
		# site-packages; the doc copy is the one the user is meant to edit
		provision_terminal_config(
			install_session,
			users,
			install_session.target / 'usr/share/doc/qtile/default_config.py',
			'qtile/config.py',
			'guess_terminal()',
			template='guess_terminal("{terminal}")',
		)

	@property
	@override
	def default_greeter_type(self) -> GreeterType:
		return GreeterType.Lightdm
