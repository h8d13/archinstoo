from typing import TYPE_CHECKING, override

from archinstoo.default_profiles.desktops import provision_terminal_config
from archinstoo.default_profiles.xorg import XorgProfile
from archinstoo.lib.output import debug
from archinstoo.lib.profile.base import ProfileType

if TYPE_CHECKING:
	from archinstoo.lib.installer import Installer
	from archinstoo.lib.models.users import User


class AwesomeProfile(XorgProfile):
	needs_terminal = True

	def __init__(self) -> None:
		super().__init__('awesome', ProfileType.WindowMgr)

	@property
	@override
	def packages(self) -> list[str]:
		# TODO: Configure the right-click-menu to contain the packages below
		# that were installed. (as a user config)
		return [
			*super().packages,
			'awesome',
			'xorg-xinit',
			'xorg-xrandr',
			'feh',
			'slock',
			'terminus-font',
			'gnu-free-fonts',
			'ttf-liberation',
			'xsel',
		]

	@override
	def provision(self, install_session: Installer, users: list[User]) -> None:
		# rc.lua hardcodes `terminal = "xterm"` and everything else reads that
		# variable; awesome prefers the ~/.config copy over the packaged one
		provision_terminal_config(
			install_session,
			users,
			install_session.target / 'etc/xdg/awesome/rc.lua',
			'awesome/rc.lua',
			'xterm',
		)

		# TODO: check if we selected a greeter,
		# but for now, awesome is intended to run without one.

		# startx prefers ~/.xinitrc over the packaged /etc/X11/xinit/xinitrc,
		# whose twm/xclock/xterm session this profile installs none of
		for user in users:
			xinitrc = install_session.target / 'home' / user.username / '.xinitrc'
			xinitrc.parent.mkdir(parents=True, exist_ok=True)
			xinitrc.write_text('exec awesome\n')
			debug(f'Wrote {xinitrc}')

			install_session.chown_tree(user.username, f'/home/{user.username}/.xinitrc')
