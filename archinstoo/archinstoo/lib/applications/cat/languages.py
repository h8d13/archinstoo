from typing import TYPE_CHECKING, ClassVar

from archinstoo.lib.models.application import Language
from archinstoo.lib.output import debug

if TYPE_CHECKING:
	from archinstoo.lib.installer import Installer
	from archinstoo.lib.models.application import LanguageConfiguration


class LanguagesApp:
	# toolchains needing more than their own package name; others map to [tool.value]
	_extra_packages: ClassVar[dict[Language, list[str]]] = {
		Language.CLANG: ['clang', 'lld'],
	}

	def install(
		self,
		install_session: Installer,
		language_config: LanguageConfiguration,
	) -> None:
		debug(f'Installing languages: {[t.value for t in language_config.tools]}')

		packages: list[str] = []
		for tool in language_config.tools:
			packages += self._extra_packages.get(tool, [tool.value])

		if packages:
			install_session.add_additional_packages(packages)
