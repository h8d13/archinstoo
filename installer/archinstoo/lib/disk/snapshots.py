import textwrap
from typing import TYPE_CHECKING

from archinstoo.lib.chroot import chroot_prefix
from archinstoo.lib.exceptions import DiskError, SysCallError
from archinstoo.lib.general import SysCommand
from archinstoo.lib.models.bootloader import Bootloader
from archinstoo.lib.models.device import SnapshotType
from archinstoo.lib.output import debug, info

if TYPE_CHECKING:
	from pathlib import Path

	from archinstoo.lib.installer import Installer

# grub integration for either snapshot tool
__grub_snapshot_packages__ = ['grub-btrfs', 'inotify-tools']


def setup_btrfs_snapshot(
	installation: Installer,
	snapshot_type: SnapshotType,
	bootloader: Bootloader | None = None,
) -> None:
	if snapshot_type == SnapshotType.Snapper:
		debug('Setting up Btrfs snapper')
		installation.pacman.strap(snapshot_type.packages)

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

		installation.pacman.strap(snapshot_type.packages)
		installation.enable_service('cronie')

	if bootloader and bootloader == Bootloader.Grub:
		debug('Setting up grub integration for either')
		installation.pacman.strap(__grub_snapshot_packages__)
		_configure_grub_btrfsd(installation.target, snapshot_type)
		installation.enable_service('grub-btrfsd')


def _configure_grub_btrfsd(target: Path, snapshot_type: SnapshotType) -> None:
	if snapshot_type == SnapshotType.Timeshift:
		snapshot_path = '--timeshift-auto'
	elif snapshot_type == SnapshotType.Snapper:
		snapshot_path = '/.snapshots'
	else:
		raise ValueError('Unsupported snapshot type')

	debug(f'Configuring grub-btrfsd service for {snapshot_type} at {snapshot_path}')

	# Works for either snapper or ts just adapting default paths above
	# https://www.freedesktop.org/software/systemd/man/latest/systemd.unit.html#id-1.14.3
	systemd_dir = target / 'etc/systemd/system/grub-btrfsd.service.d'
	systemd_dir.mkdir(parents=True, exist_ok=True)

	override_conf = systemd_dir / 'override.conf'

	config_content = textwrap.dedent(
		"""
		[Service]
		ExecStart=
		ExecStart=/usr/bin/grub-btrfsd --syslog {snapshot_path}
		"""
	).format(snapshot_path=snapshot_path)

	override_conf.write_text(config_content)
	override_conf.chmod(0o644)
