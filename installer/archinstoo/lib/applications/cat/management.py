from typing import TYPE_CHECKING

from archinstoo.lib.models.applications import Management
from archinstoo.lib.output import debug

if TYPE_CHECKING:
	from archinstoo.lib.installer import Installer
	from archinstoo.lib.models.applications import ManagementConfiguration

_NTSYNC_CONF = 'etc/modules-load.d/ntsync.conf'


class ManagementApp:
	def install(
		self,
		install_session: Installer,
		management_config: ManagementConfiguration,
	) -> None:
		debug(f'Installing management tools: {[t.value for t in management_config.tools]}')

		packages = [tool.value for tool in management_config.tools if tool != Management.NTSYNC]
		if packages:
			install_session.add_additional_packages(packages)

		if Management.NTSYNC in management_config.tools:
			conf = install_session.target / _NTSYNC_CONF
			conf.parent.mkdir(parents=True, exist_ok=True)
			conf.write_text('ntsync\n')
			debug(f'Wrote {conf}')
