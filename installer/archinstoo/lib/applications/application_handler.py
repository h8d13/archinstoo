from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from archinstoo.lib.output import info

from .cat.audio import AudioApp
from .cat.bluetooth import BluetoothApp
from .cat.cpu_scheduler import CPUSchedulerApp
from .cat.editor import EditorApp
from .cat.firewall import FirewallApp
from .cat.flatpak import FlatpakApp
from .cat.management import ManagementApp
from .cat.media_codecs import MediaCodecsApp
from .cat.monitor import MonitorApp
from .cat.power_management import PowerManagementApp
from .cat.print_service import PrintServiceApp
from .cat.security import SecurityApp
from .cat.terminal import TerminalApp
from .cat.thunderbolt import ThunderboltApp

if TYPE_CHECKING:
	from archinstoo.lib.installer import Installer
	from archinstoo.lib.models.applications import ApplicationConfiguration
	from archinstoo.lib.models.users import User


@dataclass(frozen=True)
class Category:
	# the ApplicationConfiguration field this category's config sits in
	key: str
	app: type[Any]
	# schema.toml section, where it is not the key less its _config
	section: str = ''
	# install() also takes the users (audio enables per-user units)
	users: bool = False

	@property
	def name(self) -> str:
		return self.section or self.key.removesuffix('_config')


# every application category, in install order (apps run before bootloader,
# after users). install_applications walks this and so do the app sections of
# schema.toml (schema_gen._app_sections), so a category is registered here once
CATEGORIES: tuple[Category, ...] = (
	Category('bluetooth_config', BluetoothApp),
	Category('thunderbolt_config', ThunderboltApp),
	Category('audio_config', AudioApp, users=True),
	Category('media_codecs_config', MediaCodecsApp),
	Category('flatpak_config', FlatpakApp),
	Category('power_management_config', PowerManagementApp),
	Category('cpu_scheduler_config', CPUSchedulerApp),
	Category('print_service_config', PrintServiceApp, section='printing'),
	Category('firewall_config', FirewallApp, section='firewalls'),
	Category('management_config', ManagementApp),
	Category('monitor_config', MonitorApp, section='monitors'),
	Category('editor_config', EditorApp, section='editors'),
	Category('terminal_config', TerminalApp, section='terminals'),
	Category('security_config', SecurityApp),
)


def install_applications(
	install_session: Installer,
	app_config: ApplicationConfiguration,
	users: list[User] | None = None,
) -> None:
	info('Installing applications', step=True)

	for cat in CATEGORIES:
		config = getattr(app_config, cat.key)
		if config is None:
			continue

		# one field per category (models/applications._Category): a flag, a
		# choice or a list of them. off and empty install nothing
		(value,) = vars(config).values()
		if not value:
			continue

		if isinstance(value, bool):
			cat.app().install(install_session)
		elif cat.users:
			cat.app().install(install_session, config, users)
		else:
			cat.app().install(install_session, config)
