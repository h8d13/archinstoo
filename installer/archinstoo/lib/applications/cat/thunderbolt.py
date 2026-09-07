from typing import TYPE_CHECKING

from archinstoo.lib.output import debug

if TYPE_CHECKING:
	from archinstoo.lib.installer import Installer


class ThunderboltApp:
	@property
	def packages(self) -> list[str]:
		# boltd flips authorized=1 for enrolled devices in the firmware's
		# user/secure levels; gnome-control-center already depends on it,
		# plasma-thunderbolt pulls it, this covers WM/minimal installs
		return ['bolt']

	def install(self, install_session: Installer) -> None:
		debug('Installing Thunderbolt device authorization')
		install_session.add_additional_packages(self.packages)
