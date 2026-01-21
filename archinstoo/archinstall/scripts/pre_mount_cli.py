"""
Pre-mount CLI installer from issue #4149.
"""

import argparse
from pathlib import Path

from archinstall.lib.installer import Installer
from archinstall.lib.models.device import DiskLayoutConfiguration, DiskLayoutType


def main() -> None:
	parser = argparse.ArgumentParser()
	parser.add_argument('--timezone')
	parser.add_argument('--hostname')
	parser.add_argument('mountpoint', type=Path)
	args = parser.parse_args()

	installer = Installer(
		args.mountpoint,
		DiskLayoutConfiguration(DiskLayoutType.Pre_mount),
	)

	if args.timezone:
		installer.set_timezone(args.timezone)

	if args.hostname:
		installer.set_hostname(args.hostname)


main()
