from typing import TYPE_CHECKING

from archinstoo.lib.models import Audio
from archinstoo.lib.models.application import ApplicationConfiguration
from archinstoo.lib.models.users import User

from .cat.audio import AudioApp
from .cat.bluetooth import BluetoothApp
from .cat.editor import EditorApp
from .cat.firewall import FirewallApp
from .cat.management import ManagementApp
from .cat.monitor import MonitorApp
from .cat.power_management import PowerManagementApp
from .cat.print_service import PrintServiceApp
from .cat.security import SecurityApp

if TYPE_CHECKING:
	from archinstoo.lib.installer import Installer


class ApplicationHandler:
	def __init__(self) -> None:
		pass

	def install_applications(self, install_session: Installer, app_config: ApplicationConfiguration, users: list[User] | None = None) -> None:
		if app_config.bluetooth_config and app_config.bluetooth_config.enabled:
			BluetoothApp().install(install_session)

		if app_config.audio_config and app_config.audio_config.audio != Audio.NO_AUDIO:
			AudioApp().install(
				install_session,
				app_config.audio_config,
				users,
			)

		if app_config.power_management_config:
			PowerManagementApp().install(
				install_session,
				app_config.power_management_config,
			)

		if app_config.print_service_config and app_config.print_service_config.enabled:
			PrintServiceApp().install(install_session)

		if app_config.firewall_config:
			FirewallApp().install(
				install_session,
				app_config.firewall_config,
			)

		if app_config.management_config and app_config.management_config.tools:
			ManagementApp().install(
				install_session,
				app_config.management_config,
			)

		if app_config.monitor_config:
			MonitorApp().install(
				install_session,
				app_config.monitor_config,
			)

		if app_config.editor_config:
			EditorApp().install(
				install_session,
				app_config.editor_config,
			)

		if app_config.security_config and app_config.security_config.enabled:
			SecurityApp().install(install_session)
