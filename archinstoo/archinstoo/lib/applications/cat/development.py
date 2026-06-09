from typing import TYPE_CHECKING, ClassVar

from archinstoo.lib.models.application import Development
from archinstoo.lib.output import debug

if TYPE_CHECKING:
	from archinstoo.lib.installer import Installer
	from archinstoo.lib.models.application import DevelopmentConfiguration


class DevelopmentApp:
	# tools needing more than their own package name; others map to [tool.value]
	_extra_packages: ClassVar[dict[Development, list[str]]] = {
		Development.NODEJS: ['nodejs', 'npm'],
		Development.CLANG: ['clang', 'lld', 'lldb'],
		Development.BUILD: ['cmake', 'make', 'ninja'],
		Development.DEBUG: ['gdb', 'perf', 'strace', 'ltrace', 'valgrind'],
	}

	def install(
		self,
		install_session: Installer,
		development_config: DevelopmentConfiguration,
	) -> None:
		debug(f'Installing development tools: {[t.value for t in development_config.tools]}')

		packages: list[str] = []
		for tool in development_config.tools:
			packages += self._extra_packages.get(tool, [tool.value])

		if packages:
			install_session.add_additional_packages(packages)
