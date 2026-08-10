from dataclasses import dataclass
from enum import StrEnum, auto
from typing import NotRequired, Self, TypedDict


class ZramAlgorithm(StrEnum):
	Default = 'default'
	ZSTD = auto()
	LZO_RLE = 'lzo-rle'
	LZO = auto()
	LZ4 = auto()
	LZ4HC = auto()


class ZramConfigSerialization(TypedDict):
	enabled: bool
	algorithm: NotRequired[str]
	recomp_algorithm: NotRequired[str]


@dataclass(frozen=True)
class ZramConfiguration:
	enabled: bool
	algorithm: ZramAlgorithm = ZramAlgorithm.Default
	recomp_algorithm: ZramAlgorithm | None = None

	@classmethod
	def parse_arg(cls, arg: bool | ZramConfigSerialization) -> Self:
		if isinstance(arg, bool):
			return cls(enabled=arg)

		enabled = arg.get('enabled', True)
		algo = arg.get('algorithm', ZramAlgorithm.Default.value)
		recomp = arg.get('recomp_algorithm')
		recomp_algo = ZramAlgorithm(recomp) if recomp else None
		return cls(enabled=enabled, algorithm=ZramAlgorithm(algo), recomp_algorithm=recomp_algo)
