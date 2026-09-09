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
		# awesome reads ~/.config/awesome/rc.lua before the packaged copy, and
		# that copy hardcodes `terminal = "xterm"`: everything else in it (menu
		# entries, menubar.utils.terminal) reads that one variable
		provision_terminal_config(
			install_session,
			users,
			install_session.target / 'etc/xdg/awesome/rc.lua',
			'awesome/rc.lua',
			'xterm',
		)

		# TODO: check if we selected a greeter,
		# but for now, awesome is intended to run without one.
		#
		# startx runs ~/.xinitrc when there is one and the packaged
		# /etc/X11/xinit/xinitrc (twm, xclock and three xterms, none of which
		# this profile installs) when there is not. Owning the per-user file
		# leaves the packaged one alone: no rewrite to keep in sync with
		# upstream, and no .pacnew on the next xorg-xinit release
		for user in users:
			xinitrc = install_session.target / 'home' / user.username / '.xinitrc'
			xinitrc.parent.mkdir(parents=True, exist_ok=True)
			xinitrc.write_text('exec awesome\n')
			debug(f'Wrote {xinitrc}')

			install_session.chown_tree(user.username, f'/home/{user.username}/.xinitrc')
