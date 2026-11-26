from typing import TYPE_CHECKING

from archinstoo.lib.output import debug

if TYPE_CHECKING:
	from archinstoo.lib.installer import Installer
	from archinstoo.lib.models.applications import MonitorConfiguration


class MonitorApp:
	def install(
		self,
		install_session: Installer,
		monitor_config: MonitorConfiguration,
	) -> None:
		monitor = monitor_config.monitor
		debug(f'Installing monitor: {monitor.value}')

		# every option is its own package
		install_session.add_additional_packages([monitor.value])
