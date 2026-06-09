from typing import TYPE_CHECKING

from archinstoo.lib.output import debug

if TYPE_CHECKING:
	from archinstoo.lib.installer import Installer
	from archinstoo.lib.models.application import DevToolConfiguration


class DevToolsApp:
	def install(
		self,
		install_session: Installer,
		devtool_config: DevToolConfiguration,
	) -> None:
		# à la carte: each tool's enum value is its package name
		packages = [tool.value for tool in devtool_config.tools]
		debug(f'Installing dev tools: {packages}')

		if packages:
			install_session.add_additional_packages(packages)
