from dataclasses import dataclass
from typing import NotRequired, Self, TypedDict

# dnf5's own range for max_parallel_downloads
# https://dnf5.readthedocs.io/en/latest/dnf5.conf.5.html#max-parallel-downloads-options-label
PARALLEL_DOWNLOADS_RANGE = range(1, 21)


class DnfConfigSerialization(TypedDict):
	install_weak_deps: NotRequired[bool]
	max_parallel_downloads: NotRequired[int | None]


@dataclass
class DnfConfiguration:
	# applied to every strap (--setopt) and written to the target's dnf.conf,
	# so the installed system resolves the way its install did. The base and
	# kernel straps pin weak deps themselves (Installer). Defaults are dnf5's
	# own: weak deps on, parallel downloads left to dnf (3)
	# https://dnf5.readthedocs.io/en/latest/dnf5.conf.5.html#install-weak-deps-options-label
	install_weak_deps: bool = True
	max_parallel_downloads: int | None = None

	def options(self) -> dict[str, str]:
		options = {'install_weak_deps': 'True' if self.install_weak_deps else 'False'}
		if self.max_parallel_downloads is not None:
			options['max_parallel_downloads'] = str(self.max_parallel_downloads)
		return options

	def json(self) -> DnfConfigSerialization:
		return {
			'install_weak_deps': self.install_weak_deps,
			'max_parallel_downloads': self.max_parallel_downloads,
		}

	@classmethod
	def parse_arg(cls, arg: DnfConfigSerialization) -> Self:
		parallel = arg.get('max_parallel_downloads')
		if parallel is not None and parallel not in PARALLEL_DOWNLOADS_RANGE:
			raise ValueError(f'max_parallel_downloads must be within 1-20, got {parallel}')
		return cls(
			install_weak_deps=arg.get('install_weak_deps', True),
			max_parallel_downloads=parallel,
		)

	def preview(self) -> str:
		parallel = self.max_parallel_downloads or 'dnf default (3)'
		return f'Weak dependencies: {"Enabled" if self.install_weak_deps else "Disabled"}\nParallel downloads: {parallel}\n'
