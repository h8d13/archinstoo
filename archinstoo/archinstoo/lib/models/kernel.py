from dataclasses import dataclass, field
from typing import NotRequired, Self, TypedDict

from archinstoo.lib.translationhandler import tr


class KernelConfigSerialization(TypedDict):
	kernels: list[str]
	headers: NotRequired[bool]


@dataclass
class KernelConfiguration:
	kernels: list[str] = field(default_factory=lambda: ['linux'])
	headers: bool = False

	def json(self) -> KernelConfigSerialization:
		config: KernelConfigSerialization = {'kernels': self.kernels}
		if self.headers:
			config['headers'] = self.headers
		return config

	@classmethod
	def parse_arg(cls, arg: KernelConfigSerialization) -> Self:
		return cls(
			kernels=arg.get('kernels', ['linux']),
			headers=arg.get('headers', False),
		)

	def preview(self) -> str:
		kernel = ', '.join(self.kernels) if self.kernels else tr('None')
		output = f'{tr("Kernels")}: {kernel}\n'
		status = tr('Enabled') if self.headers else tr('Disabled')
		output += f'{tr("Headers")}: {status}'
		return output
