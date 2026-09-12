from typing import TYPE_CHECKING

from archinstoo.lib.output import info

if TYPE_CHECKING:
	from pathlib import Path


def write_sysctl(target: Path, entries: list[str]) -> None:
	# one drop-in for every tunable the config asked for; nothing written
	# when there are none, so a stock target stays stock
	if not entries:
		return

	info('Writing sysctl configuration')
	sysctl_dir = target / 'etc/sysctl.d'
	sysctl_dir.mkdir(parents=True, exist_ok=True)

	conf = sysctl_dir / '99-archinstoo.conf'
	conf.write_text('\n'.join(entries) + '\n')
