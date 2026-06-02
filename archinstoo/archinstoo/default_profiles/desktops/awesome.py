from typing import TYPE_CHECKING, override

from archinstoo.default_profiles.xorg import XorgProfile
from archinstoo.lib.profile.base import ProfileType

if TYPE_CHECKING:
	from archinstoo.lib.installer import Installer


class AwesomeProfile(XorgProfile):
	def __init__(self) -> None:
		super().__init__('awesome', ProfileType.WindowMgr)

	@property
	@override
	def packages(self) -> list[str]:
		return super().packages + [
			'awesome',
			'alacritty',
			'xorg-xinit',
			'xorg-xrandr',
			'xterm',
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

		# TODO: Copy a full configuration to ~/.config/awesome/rc.lua instead.
		rc_lua_path = install_session.target / 'etc/xdg/awesome/rc.lua'
		with rc_lua_path.open() as fh:
			awesome_lua = fh.read()

		# Replace xterm with alacritty for a smoother experience.
		awesome_lua = awesome_lua.replace('"xterm"', '"alacritty"')

		with rc_lua_path.open('w') as fh:
			fh.write(awesome_lua)

		# TODO: Configure the right-click-menu to contain the above packages that were installed. (as a user config)

		# TODO: check if we selected a greeter,
		# but for now, awesome is intended to run without one.
		xinitrc_path = install_session.target / 'etc/X11/xinit/xinitrc'
		with xinitrc_path.open() as xinitrc:
			xinitrc_data = xinitrc.read()

		for line in xinitrc_data.split('\n'):
			if 'twm &' in line:
				xinitrc_data = xinitrc_data.replace(line, f'# {line}')
			if 'xclock' in line:
				xinitrc_data = xinitrc_data.replace(line, f'# {line}')
			if 'xterm' in line:
				xinitrc_data = xinitrc_data.replace(line, f'# {line}')

		xinitrc_data += '\n'
		xinitrc_data += 'exec awesome\n'

		with xinitrc_path.open('w') as xinitrc:
			xinitrc.write(xinitrc_data)
