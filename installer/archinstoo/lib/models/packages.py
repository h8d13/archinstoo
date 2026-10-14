from dataclasses import asdict, dataclass


# slotted: list_available_packages() holds one per repo package (~70k)
@dataclass(slots=True)
class AvailablePackage:
	name: str
	version: str
	release: str
	architecture: str
	repository: str
	summary: str
	description: str
	url: str
	license: str
	download_size: str
	installed_size: str

	def info(self) -> str:
		values = asdict(self)
		width = max(len(key) for key in values)
		output = ''
		for key, value in values.items():
			label = key.replace('_', ' ').capitalize().ljust(width)
			output += f'{label} : {value}\n'

		return output


@dataclass
class PackageGroup:
	# a comps group, installed as @<id>; dnf resolves its members at install
	name: str
	description: str = ''

	def info(self) -> str:
		return f'Package group: {self.description}\nMembers are resolved by dnf at install time.'
