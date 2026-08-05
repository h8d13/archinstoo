from typing import TYPE_CHECKING

from .cat.audio import AudioApp
from .cat.bluetooth import BluetoothApp
from .cat.devtools import DevToolsApp
from .cat.editor import EditorApp
from .cat.firewall import FirewallApp
from .cat.languages import LanguagesApp
from .cat.management import ManagementApp
from .cat.monitor import MonitorApp
from .cat.power_management import PowerManagementApp
from .cat.print_service import PrintServiceApp
from .cat.security import SecurityApp

if TYPE_CHECKING:
	from archinstoo.lib.installer import Installer
	from archinstoo.lib.models.application import ApplicationConfiguration
	from archinstoo.lib.models.users import User


class ApplicationHandler:
	def __init__(self) -> None:
		pass

	def install_applications(self, install_session: Installer, app_config: ApplicationConfiguration, users: list[User] | None = None) -> None:
		if app_config.bluetooth_config and app_config.bluetooth_config.enabled:
			BluetoothApp().install(install_session)

		if app_config.audio_config:
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

		if app_config.security_config and app_config.security_config.tools:
			SecurityApp().install(
				install_session,
				app_config.security_config,
			)

		if app_config.development_config:
			dev_config = app_config.development_config

			if dev_config.language_config and dev_config.language_config.tools:
				LanguagesApp().install(
					install_session,
					dev_config.language_config,
				)

			if dev_config.devtool_config and dev_config.devtool_config.tools:
				DevToolsApp().install(
					install_session,
					dev_config.devtool_config,
				)
