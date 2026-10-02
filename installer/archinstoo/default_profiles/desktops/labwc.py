from typing import TYPE_CHECKING, override

from archinstoo.default_profiles.desktops import select_seat_access
from archinstoo.default_profiles.wayland import WaylandProfile
from archinstoo.lib.profile.base import ProfileType, seat_packages, seat_services

if TYPE_CHECKING:
	from archinstoo.lib.installer import Installer


class LabwcProfile(WaylandProfile):
	needs_terminal = True

	def __init__(self) -> None:
		super().__init__(
			'labwc',
			ProfileType.WindowMgr,
		)

		self.custom_settings = {'seat_access': None}

	@property
	@override
	def packages(self) -> list[str]:
		return [
			'labwc',
			*seat_packages(self.custom_settings.get('seat_access')),
			'xdg-desktop-portal-wlr',  # labwc-portals.conf: default=wlr; labwc pulls no backend
		]

	@override
	def install(self, install_session: Installer) -> None:
		super().install(install_session)

		# xdg-desktop-portal-wlr only starts once the systemd user session knows the
		# compositor; sway ships a drop-in for this, labwc leaves it to autostart
		autostart = install_session.target / 'etc/xdg/labwc/autostart'
		autostart.parent.mkdir(parents=True, exist_ok=True)
		line = 'systemctl --user import-environment WAYLAND_DISPLAY XDG_CURRENT_DESKTOP && '
		line += 'dbus-update-activation-environment --systemd WAYLAND_DISPLAY XDG_CURRENT_DESKTOP\n'
		existing = autostart.read_text() if autostart.is_file() else ''
		if 'import-environment' not in existing:
			autostart.write_text(existing + line)
			autostart.chmod(0o755)

	@property
	@override
	def services(self) -> list[str]:
		return seat_services(self.custom_settings.get('seat_access'))

	@override
	def do_on_select(self) -> None:
		self.custom_settings['seat_access'] = select_seat_access(
			'labwc',
			self.custom_settings.get('seat_access'),
		)
