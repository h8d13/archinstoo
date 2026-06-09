from typing import TYPE_CHECKING

from archinstoo.lib.output import debug

if TYPE_CHECKING:
	from archinstoo.lib.installer import Installer
	from archinstoo.lib.models.application import LanguageConfiguration


class LanguagesApp:
	def install(
		self,
		install_session: Installer,
		language_config: LanguageConfiguration,
	) -> None:
		debug(f'Installing languages: {[t.value for t in language_config.tools]}')

		packages = [tool.value for tool in language_config.tools]
		if packages:
			install_session.add_additional_packages(packages)
