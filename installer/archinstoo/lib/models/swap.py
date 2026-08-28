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


class SwapConfigSerialization(TypedDict):
	zram: bool
	algorithm: NotRequired[str]
	recomp_algorithm: NotRequired[str]
	hibernation: NotRequired[bool]
	size_gib: NotRequired[int]


# zram and the hibernation swap file compose, they don't compete: zram takes
# the everyday swapping (zram-generator's default priority 100 outranks the
# file's -2) while logind ignores zram devices and hibernates into the file.
@dataclass(frozen=True)
class SwapConfiguration:
	zram: bool = True
	# zram only
	algorithm: ZramAlgorithm = ZramAlgorithm.Default
	recomp_algorithm: ZramAlgorithm | None = None
	# disk-backed swap file, the hibernation image target; on by default so
	# hibernation works out of the box (upstream archinstall #994)
	hibernation: bool = True
	# 0 sizes the file to RAM so the image always fits
	size_gib: int = 0

	@property
	def enabled(self) -> bool:
		return self.zram or self.hibernation

	@classmethod
	def parse_arg(cls, arg: SwapConfigSerialization) -> Self:
		recomp = arg.get('recomp_algorithm')
		return cls(
			zram=arg['zram'],
			algorithm=ZramAlgorithm(arg.get('algorithm', ZramAlgorithm.Default.value)),
			recomp_algorithm=ZramAlgorithm(recomp) if recomp else None,
			hibernation=arg.get('hibernation', True),
			size_gib=arg.get('size_gib', 0),
		)
