import re
from enum import StrEnum, auto
from typing import Final


class Kernel(StrEnum):
	# Fedora builds one; anything else (COPR kernels) is a custom name
	KERNEL = auto()


DEFAULT_KERNEL: Final = Kernel.KERNEL

# rpm names: alnum and ._+-, mixed case allowed (NetworkManager), no
# leading - or .
_PACKAGE_NAME = re.compile(r'[A-Za-z0-9_+][A-Za-z0-9._+-]*')


def kernel_names_error(text: str | None) -> str | None:
	# None when every space separated name could be a package. Syntax only:
	# the menu asks the repos after (pm.missing_packages)
	names = (text or '').split()
	if not names:
		return 'Type at least one package name'
	for name in names:
		if not _PACKAGE_NAME.fullmatch(name):
			return f'{name!r} is not a valid package name'
	return None
