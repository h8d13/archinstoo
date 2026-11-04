from typing import TYPE_CHECKING, override

from archinstoo.default_profiles.wayland import WaylandProfile
from archinstoo.lib.profile.base import GreeterType, ProfileType

if TYPE_CHECKING:
	from archinstoo.lib.installer import Installer


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
			# io.elementary.dock, which gala launches; plank (a
			# pantheon-session dep) is X11 only
			'pantheon-dock',
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
			# no wingpanel-indicator-power: Arch pins a commit mid
			# schema rename (upstream d59ea9c finishes it), its
			# widgets ask for the old id and abort wingpanel
			'wingpanel-indicator-notifications',
			'wingpanel-indicator-keyboard',
		]

	@override
	def install(self, install_session: Installer) -> None:
		super().install(install_session)

		# gnome-session also ships gnome.desktop, which needs gnome-shell;
		# point the greeter at pantheon's own session. lightdm reads
		# drop-ins from /etc/xdg, never /etc/lightdm/lightdm.conf.d
		conf = install_session.target / (
			'etc/xdg/lightdm/lightdm.conf.d/50-pantheon.conf'
		)
		conf.parent.mkdir(parents=True, exist_ok=True)
		conf.write_text('[Seat:*]\nuser-session=pantheon-wayland\n')

		# the dock's default launchers are elementary OS's app set, of
		# which only files is installed here; pin what this profile
		# ships. packages are already in, so their schema hook ran
		schemas = install_session.target / 'usr/share/glib-2.0/schemas'
		(schemas / '50_archinstoo-pantheon.gschema.override').write_text(
			'[io.elementary.dock:Pantheon]\n'
			"launchers=['io.elementary.files.desktop', "
			"'io.elementary.terminal.desktop', "
			"'io.elementary.settings.desktop']\n"
		)
		install_session.arch_chroot(
			['glib-compile-schemas', '/usr/share/glib-2.0/schemas']
		)

	@property
	@override
	def default_greeter_type(self) -> GreeterType:
		# lightdm-pantheon-greeter 8.1.2 cannot run on mutter 49: X11
		# mode has no backend, wayland mode segfaults (upstream moved
		# the greeter onto gala, unreleased)
		return GreeterType.Lightdm
