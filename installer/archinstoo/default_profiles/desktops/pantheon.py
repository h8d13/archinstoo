from typing import override

from archinstoo.default_profiles.wayland import WaylandProfile
from archinstoo.lib.profile.base import GreeterType, ProfileType


class PantheonProfile(WaylandProfile):
	def __init__(self) -> None:
		super().__init__('pantheon', ProfileType.DesktopEnv)

	@property
	@override
	def packages(self) -> list[str]:
		# composed instead of the 'pantheon' group, which pulls every
		# app (mail, music, photos...). pantheon-session already depends
		# on gala, wingpanel, plank, the applications menu, gnome-session
		# and gnome-keyring; 8.x ships only the wayland session
		return [
			'pantheon-session',
			'pantheon-polkit-agent',
			'pantheon-settings-daemon',
			# gsettings overrides (theme, fonts, keybinds) and
			# pantheon-portals.conf, named below. its wallpaper is
			# left out for weight, gala falls back to primary-color
			'pantheon-default-settings',
			'gtk-theme-elementary',
			'elementary-icon-theme',
			'sound-theme-elementary',
			'inter-font',
			'ttf-opensans',
			'ttf-roboto-mono',
			# pantheon-portals.conf: default=pantheon;gtk, the
			# pantheon backend is not packaged so gtk serves it
			'xdg-desktop-portal-gtk',
			# also the FileChooser portal backend
			'pantheon-files',
			'pantheon-terminal',
			'switchboard',
			'switchboard-plug-desktop',
			'switchboard-plug-display',
			'switchboard-plug-keyboard',
			'switchboard-plug-mouse-touchpad',
			'switchboard-plug-network',
			'switchboard-plug-sound',
			'switchboard-plug-power',
			'switchboard-plug-datetime',
			'switchboard-plug-locale',
			'switchboard-plug-user-accounts',
			'wingpanel-indicator-datetime',
			'wingpanel-indicator-network',
			'wingpanel-indicator-sound',
			'wingpanel-indicator-power',
			'wingpanel-indicator-notifications',
			'wingpanel-indicator-keyboard',
		]

	@property
	@override
	def default_greeter_type(self) -> GreeterType:
		return GreeterType.LightdmPantheon
