from typing import TYPE_CHECKING

from archinstoo.lib.models.sysctl import BASE_DEFAULTS, DEFAULTS_CONF, ENTRIES_CONF, SysctlConfiguration
from archinstoo.lib.output import info

if TYPE_CHECKING:
	from collections.abc import Sequence
	from pathlib import Path


def write_sysctl(target: Path, name: str, entries: Sequence[str]) -> None:
	# one drop-in per source; nothing written when there are no entries,
	# so a stock target stays stock
	if not entries:
		return

	info(f'Writing sysctl configuration {name}.conf')
	sysctl_dir = target / 'etc/sysctl.d'
	sysctl_dir.mkdir(parents=True, exist_ok=True)
	(sysctl_dir / f'{name}.conf').write_text('\n'.join(entries) + '\n')


def setup_sysctl(target: Path, config: SysctlConfiguration) -> None:
	if config.optimized:
		write_sysctl(target, DEFAULTS_CONF, BASE_DEFAULTS)
	write_sysctl(target, ENTRIES_CONF, config.entries)
