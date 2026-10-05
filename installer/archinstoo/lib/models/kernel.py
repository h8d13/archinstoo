import re
from enum import StrEnum, auto
from typing import Final


class Kernel(StrEnum):
	LINUX = auto()
	LINUX_LTS = 'linux-lts'
	LINUX_ZEN = 'linux-zen'
	LINUX_HARDENED = 'linux-hardened'
	LINUX_RT = 'linux-rt'
	LINUX_RT_LTS = 'linux-rt-lts'


DEFAULT_KERNEL: Final = Kernel.LINUX

# pacman's package name charset: lowercase alnum and @._+-, no leading - or .
_PACKAGE_NAME = re.compile(r'[a-z0-9@_+][a-z0-9@._+-]*')


def kernel_names_error(text: str | None) -> str | None:
	# None when every space separated name could be a package; whether the
	# repos carry it is left to pacstrap, as for a config's kernels
	names = (text or '').split()
	if not names:
		return 'Type at least one package name'
	for name in names:
		if not _PACKAGE_NAME.fullmatch(name):
			return f'{name!r} is not a valid package name'
	return None
