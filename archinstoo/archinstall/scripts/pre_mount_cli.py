"""
Pre-mount CLI installer from GitHub issue #4149.
"""

import argparse
from pathlib import Path

from archinstall.lib.args import ArchConfig, ArchConfigHandler, Arguments
from archinstall.lib.installer import Installer
from archinstall.lib.models.device import DiskLayoutConfiguration, DiskLayoutType


class MinimalConfigHandler(ArchConfigHandler):
	"""A minimal config handler for pre-mount installs that doesn't parse CLI args."""

	def __init__(self, mountpoint: Path) -> None:  # pylint: disable=super-init-not-called
		# Intentionally don't call super().__init__() to avoid CLI arg parsing
		self._args = Arguments(mountpoint=mountpoint)
		self._config = ArchConfig()


def main() -> None:
	parser = argparse.ArgumentParser()
	parser.add_argument('--timezone')
	parser.add_argument('--hostname')
	parser.add_argument('mountpoint', type=Path)
	args = parser.parse_args()

	handler = MinimalConfigHandler(args.mountpoint)

	disk_config = DiskLayoutConfiguration(
		config_type=DiskLayoutType.Pre_mount,
		mountpoint=args.mountpoint,
	)

	with Installer(
		args.mountpoint,
		disk_config,
		handler=handler,
	) as installer:
		if args.timezone:
			installer.set_timezone(args.timezone)

		if args.hostname:
			installer.set_hostname(args.hostname)


main()
