from typing import TYPE_CHECKING, override

from archinstoo.default_profiles.desktops import swap_terminal
from archinstoo.default_profiles.xorg import XorgProfile
from archinstoo.lib.output import debug, warn
from archinstoo.lib.profile.base import ProfileType

if TYPE_CHECKING:
	from archinstoo.lib.installer import Installer


class AwesomeProfile(XorgProfile):
	needs_terminal = True

	def __init__(self) -> None:
		super().__init__('awesome', ProfileType.WindowMgr)

	@property
	@override
	def packages(self) -> list[str]:
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
	def install(self, install_session: Installer) -> None:
		super().install(install_session)

		# two independent files: a missing rc.lua must not cost the xinitrc
		# rewrite, which is what starts awesome (this profile ships no greeter)
		self._swap_rc_lua_terminal(install_session)
		self._exec_awesome_from_xinitrc(install_session)

	# TODO: Copy a full configuration to ~/.config/awesome/rc.lua instead.
	# TODO: Configure the right-click-menu to contain the above packages that were installed. (as a user config)
	def _swap_rc_lua_terminal(self, install_session: Installer) -> None:
		rc_lua_path = install_session.target / 'etc/xdg/awesome/rc.lua'
		if not rc_lua_path.exists():
			warn(f'{rc_lua_path} missing, leaving awesome config as shipped')
			return

		# rc.lua hardcodes `terminal = "xterm"`, and everything else in it
		# (menu entries, menubar.utils.terminal) reads that one variable
		rc_lua_path.write_text(swap_terminal(rc_lua_path.read_text(), 'xterm', rc_lua_path))
		debug(f'Rewrote {rc_lua_path}')

	# TODO: check if we selected a greeter,
	# but for now, awesome is intended to run without one.
	def _exec_awesome_from_xinitrc(self, install_session: Installer) -> None:
		xinitrc_path = install_session.target / 'etc/X11/xinit/xinitrc'
		if not xinitrc_path.exists():
			warn(f'{xinitrc_path} missing, leaving xinitrc as shipped')
			return

		xinitrc_data = xinitrc_path.read_text()

		# one pass per line: a line matching twice would get commented twice
		for line in xinitrc_data.split('\n'):
			if 'twm &' in line or 'xclock' in line or 'xterm' in line:
				xinitrc_data = xinitrc_data.replace(line, f'# {line}')

		xinitrc_path.write_text(xinitrc_data + '\nexec awesome\n')
		debug(f'Rewrote {xinitrc_path} to exec awesome')
