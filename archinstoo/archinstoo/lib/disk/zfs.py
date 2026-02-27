import os
from pathlib import Path

from archinstoo.lib.exceptions import SysCallError
from archinstoo.lib.general import SysCommand
from archinstoo.lib.models.device import ZfsDatasetConfig
from archinstoo.lib.output import debug, error, info

# Standard pool creation options matching the reference implementation
DEFAULT_POOL_OPTIONS: list[str] = [
	'-o ashift=12',
	'-O acltype=posixacl',
	'-O relatime=on',
	'-O xattr=sa',
	'-o autotrim=on',
	'-O dnodesize=auto',
	'-O normalization=formD',
	'-O devices=off',
	'-m none',
]

# ZFS services to enable on the target system
ZFS_SERVICES: list[str] = [
	'zfs.target',
	'zfs-import.target',
	'zfs-volumes.target',
	'zfs-import-scan.service',
	'zfs-zed.service',
]


def zfs_load_module() -> None:
	"""Load the ZFS kernel module."""
	debug('Loading ZFS kernel module')
	try:
		SysCommand('modprobe zfs')
		info('ZFS module loaded successfully')
	except SysCallError as e:
		error(f'Failed to load ZFS module: {e}')
		raise


def zpool_create(pool_name: str, device: Path, compression: str = 'lz4', mountpoint: Path = Path('/mnt')) -> None:
	"""Create a ZFS pool with standard options."""
	debug(f'Creating ZFS pool {pool_name} on {device}')

	options = DEFAULT_POOL_OPTIONS.copy()
	options.append(f'-O compression={compression}')
	options.append(f'-R {mountpoint}')

	cmd = f'zpool create -f {" ".join(options)} {pool_name} {device}'

	try:
		SysCommand(cmd)
		info(f'Created pool {pool_name}')
	except SysCallError as e:
		error(f'Failed to create pool: {e}')
		raise


def zpool_export(pool_name: str) -> None:
	"""Export a ZFS pool (sync, unmount all, export)."""
	debug(f'Exporting pool {pool_name}')
	try:
		os.sync()
		try:
			SysCommand('zfs umount -a')
		except SysCallError:
			debug('zfs umount -a had non-zero exit (may be expected)')
		SysCommand(f'zpool export {pool_name}')
		info(f'Pool {pool_name} exported successfully')
	except SysCallError as e:
		error(f'Failed to export pool: {e}')
		raise


def zpool_import(pool_name: str, mountpoint: Path) -> None:
	"""Import a ZFS pool at specified mountpoint without mounting datasets."""
	debug(f'Importing pool {pool_name} to {mountpoint}')
	try:
		SysCommand(f'zpool import -N -R {mountpoint} {pool_name}')
		info(f'Pool {pool_name} imported successfully')
	except SysCallError as e:
		error(f'Failed to import pool: {e}')
		raise


def zfs_create_dataset(full_path: str, properties: dict[str, str] | None = None) -> None:
	"""Create a ZFS dataset with optional properties."""
	debug(f'Creating dataset: {full_path}')

	props_str = ''
	if properties:
		props_str = ' '.join(f'-o {k}={v}' for k, v in properties.items())

	cmd = f'zfs create {props_str} {full_path}' if props_str else f'zfs create {full_path}'

	try:
		SysCommand(cmd)
	except SysCallError as e:
		error(f'Failed to create dataset {full_path}: {e}')
		raise


def zfs_create_datasets(base_dataset: str, datasets: list[ZfsDatasetConfig]) -> None:
	"""Create child datasets sorted by hierarchy depth, ensuring parents exist."""
	sorted_datasets = sorted(datasets, key=lambda d: len(d.name.split('/')))

	for dataset in sorted_datasets:
		# Ensure parent datasets exist
		parts = dataset.name.split('/')
		for i in range(len(parts) - 1):
			parent = '/'.join(parts[: i + 1])
			parent_path = f'{base_dataset}/{parent}'
			try:
				SysCommand(f'zfs list {parent_path}')
			except SysCallError:
				debug(f'Creating parent dataset: {parent_path}')
				zfs_create_dataset(parent_path, {'mountpoint': 'none'})

		full_path = f'{base_dataset}/{dataset.name}'
		props = dict(dataset.properties)
		if dataset.mountpoint:
			props['mountpoint'] = str(dataset.mountpoint)
		zfs_create_dataset(full_path, props)


def zfs_mount_dataset(dataset_path: str) -> None:
	"""Mount a specific ZFS dataset."""
	debug(f'Mounting dataset: {dataset_path}')
	try:
		SysCommand(f'zfs mount {dataset_path}')
	except SysCallError as e:
		error(f'Failed to mount dataset {dataset_path}: {e}')
		raise


def zfs_mount_all(prefix: str) -> None:
	"""Mount all datasets under a prefix (used after mounting root)."""
	debug(f'Mounting all datasets under {prefix}')
	try:
		SysCommand(f'zfs mount -R {prefix}')
	except SysCallError as e:
		# Non-fatal: some datasets may already be mounted
		debug(f'zfs mount -R had issues (may be expected): {e}')


def zfs_umount_all() -> None:
	"""Unmount all ZFS datasets."""
	debug('Unmounting all ZFS datasets')
	try:
		SysCommand('zfs umount -a')
	except SysCallError as e:
		debug(f'zfs umount -a had issues: {e}')


def zfs_set(dataset: str, prop: str, value: str) -> None:
	"""Set a property on a ZFS dataset."""
	debug(f'Setting {prop}={value} on {dataset}')
	SysCommand(f'zfs set {prop}={value} {dataset}')


def zpool_set(pool: str, prop: str, value: str) -> None:
	"""Set a property on a ZFS pool."""
	debug(f'Setting {prop}={value} on pool {pool}')
	SysCommand(f'zpool set {prop}={value} {pool}')


def zpool_set_cachefile_none(pool_name: str) -> None:
	"""Disable legacy zpool.cache (use zfs-mount-generator instead)."""
	debug(f'Setting cachefile=none on {pool_name}')
	SysCommand(f'zpool set cachefile=none {pool_name}')


def zgenhostid() -> None:
	"""Generate a static host ID for ZFS."""
	debug('Generating static hostid')
	try:
		SysCommand('zgenhostid -f 0x00bab10c')
		info('Created static hostid')
	except SysCallError as e:
		error(f'Failed to create hostid: {e}')
		raise


def zfs_load_key(pool_name: str, key_path: Path) -> None:
	"""Load encryption key for an encrypted pool."""
	debug(f'Loading encryption key for pool {pool_name}')
	try:
		SysCommand(f'zfs load-key -L file://{key_path} {pool_name}')
		info('Pool encryption key loaded successfully')
	except SysCallError as e:
		error(f'Failed to load pool encryption key: {e}')
		raise
