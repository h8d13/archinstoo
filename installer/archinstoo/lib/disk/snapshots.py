from typing import TYPE_CHECKING

from archinstoo.lib.chroot import chroot_prefix
from archinstoo.lib.exceptions import DiskError, SysCallError
from archinstoo.lib.general import SysCommand
from archinstoo.lib.models.device import SnapshotType
from archinstoo.lib.output import debug, info

if TYPE_CHECKING:
	from archinstoo.lib.installer import Installer


def setup_btrfs_snapshot(installation: Installer, snapshot_type: SnapshotType) -> None:
	if snapshot_type == SnapshotType.Snapper:
		debug('Setting up Btrfs snapper')
		installation.dnf.strap(snapshot_type.packages)

		snapper: dict[str, str] = {
			'root': '/',
			'home': '/home',
		}

		for config_name, mountpoint in snapper.items():
			# snapper create-config makes its own .snapshots subvolume and errors if one exists
			# (e.g. a manual layout that pre-created it); skip rather than abort the whole install
			if (installation.target / mountpoint.lstrip('/') / '.snapshots').exists():
				info(f'snapper: .snapshots already present at {mountpoint}, skipping create-config')
				continue

			command = [
				*chroot_prefix(installation.target),
				'snapper',
				'--no-dbus',
				'-c',
				config_name,
				'create-config',
				mountpoint,
			]

			try:
				SysCommand(command, peek_output=True)
			except SysCallError as err:
				raise DiskError(f'Could not setup Btrfs snapper: {err}') from err

		installation.enable_service('snapper-timeline.timer')
		installation.enable_service('snapper-cleanup.timer')

	elif snapshot_type == SnapshotType.Timeshift:
		debug('Setting up Btrfs timeshift')

		installation.dnf.strap(snapshot_type.packages)
		installation.enable_service('cronie')
