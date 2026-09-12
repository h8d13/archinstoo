from dataclasses import asdict, dataclass, field
from enum import Enum
from functools import cached_property
from typing import Self


class Repository(Enum):
	Core = 'core'
	Extra = 'extra'
	Multilib = 'multilib'
	Testing = 'testing'
	MultilibTesting = 'multilib-testing'
	CoreTesting = 'core-testing'
	ExtraTesting = 'extra-testing'


@dataclass
class AvailablePackage:
	name: str
	architecture: str
	build_date: str
	conflicts_with: str
	depends_on: str
	description: str
	download_size: str
	groups: str
	installed_size: str
	licenses: str
	optional_deps: str
	packager: str
	provides: str
	replaces: str
	repository: str
	url: str
	validated_by: str
	version: str

	@cached_property
	def longest_key(self) -> int:
		return max(len(key) for key in asdict(self))

	def info(self) -> str:
		output = ''
		for key, value in asdict(self).items():
			label = key.replace('_', ' ').capitalize().ljust(self.longest_key)
			output += f'{label} : {value}\n'

		return output


@dataclass
class PackageGroup:
	name: str
	packages: list[str] = field(default_factory=list)

	@classmethod
	def from_available_packages(
		cls,
		packages: dict[str, AvailablePackage],
	) -> dict[str, Self]:
		pkg_groups: dict[str, Self] = {}

		for pkg in packages.values():
			if 'None' in pkg.groups:
				continue

			groups = pkg.groups.split(' ')

			for group in groups:
				# same group names have multiple spaces in between
				if len(group) == 0:
					continue

				pkg_groups.setdefault(group, cls(group))
				pkg_groups[group].packages.append(pkg.name)

		return pkg_groups

	def info(self) -> str:
		output = 'Package group:' + '\n  - '
		output += '\n  - '.join(self.packages)
		return output
