from typing import TYPE_CHECKING, override

from archinstoo.lib.applications.cat.firewall import FirewallApp
from archinstoo.lib.profile.base import Profile, ProfileType

if TYPE_CHECKING:
	from archinstoo.lib.installer import Installer


class SshdProfile(Profile):
	def __init__(self) -> None:
		super().__init__(
			'sshd',
			ProfileType.ServerType,
		)

	@property
	@override
	def packages(self) -> list[str]:
		return ['openssh']

	@property
	@override
	def services(self) -> list[str]:
		return ['sshd']

	@override
	def install(self, install_session: Installer) -> None:
		# sshd is reachable on first boot only if the chosen firewall lets
		# 22 through; open it here so a headless install isn't locked out
		handler = install_session.handler
		if handler is None:
			return

		app_config = handler.config.app_config
		if app_config is None or app_config.firewall_config is None:
			return

		FirewallApp().allow_ssh(
			install_session,
			app_config.firewall_config.firewall,
		)
