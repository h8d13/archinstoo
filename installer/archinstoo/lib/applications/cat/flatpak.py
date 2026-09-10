from typing import TYPE_CHECKING

from archinstoo.lib.exceptions import SysCallError
from archinstoo.lib.output import debug, warn

if TYPE_CHECKING:
	from archinstoo.lib.installer import Installer


class FlatpakApp:
	@property
	def packages(self) -> list[str]:
		# sandboxed apps reach file chooser, screenshots and settings through a portal
		# backend; the gtk one is the generic fallback for desktops that ship none
		return ['flatpak', 'xdg-desktop-portal-gtk']

	def install(self, install_session: Installer) -> None:
		debug('Installing flatpak')
		install_session.add_additional_packages(self.packages)

		# system-wide fallback: a <desktop>-portals.conf (plasma, gnome, sway, ...) still
		# wins, this only catches WMs that ship none (i3, bspwm, awesome, ...)
		conf = install_session.target / 'etc/xdg/xdg-desktop-portal/portals.conf'
		conf.parent.mkdir(parents=True, exist_ok=True)
		if not conf.exists():
			conf.write_text('[preferred]\ndefault=gtk\n')

		try:
			install_session.arch_chroot(['flatpak', 'remote-add', '--if-not-exists', 'flathub', 'https://flathub.org/repo/flathub.flatpakrepo'])
		except SysCallError as err:
			warn(f'Could not add the flathub remote, add it after first boot: {err}')
