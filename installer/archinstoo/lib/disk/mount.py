from pathlib import Path

from archinstoo.lib.disk.luks import Luks2, unlock_luks2_dev
from archinstoo.lib.disk.lvm import lvm_import_vg, lvm_vol_change
from archinstoo.lib.disk.utils import mount, swapon
from archinstoo.lib.models.device import (
	DiskEncryption,
	DiskLayoutConfiguration,
	EncryptionType,
	FilesystemType,
	LvmVolume,
	PartitionModification,
	SubvolumeModification,
	harden_boot_options,
)
from archinstoo.lib.output import debug, warn


class LayoutMounter:
	# mounts a layout under target in mountpoint order, unlocking LUKS and
	# activating LVM on the way; cleanup.teardown_layout is the inverse
	def __init__(self, target: Path, disk_config: DiskLayoutConfiguration, disk_encryption: DiskEncryption) -> None:
		self.target = target
		self._disk_config = disk_config
		self._disk_encryption = disk_encryption
		self._fstab_entries: list[str] = []

	def mount(self) -> list[str]:
		# returns the fstab entries the layout needs beyond genfstab (encrypted swap)
		luks_handlers: dict[PartitionModification | LvmVolume, Luks2] = {}

		match self._disk_encryption.encryption_type:
			case EncryptionType.NO_ENCRYPTION:
				self._import_lvm()
				self._mount_lvm_layout()
			case EncryptionType.LUKS:
				luks_handlers = self._prepare_luks_partitions(self._disk_encryption.partitions)
			case EncryptionType.LVM_ON_LUKS:
				luks_handlers = self._prepare_luks_partitions(self._disk_encryption.partitions)
				self._import_lvm()
				self._mount_lvm_layout(luks_handlers)
			case EncryptionType.LUKS_ON_LVM:
				self._import_lvm()
				luks_handlers = self._prepare_luks_lvm(self._disk_encryption.lvm_volumes)
				self._mount_lvm_layout(luks_handlers)

		# mount all regular partitions
		self._mount_partition_layout(luks_handlers)
		return self._fstab_entries

	def _mount_partition_layout(self, luks_handlers: dict[PartitionModification | LvmVolume, Luks2]) -> None:
		debug('Mounting partition layout')

		# do not mount any PVs part of the LVM configuration
		pvs = []
		if self._disk_config.lvm_config:
			pvs = self._disk_config.lvm_config.get_all_pvs()

		sorted_device_mods = self._disk_config.device_modifications.copy()

		# move the device with the root partition to the beginning of the list
		for mod in self._disk_config.device_modifications:
			if any(partition.is_root() for partition in mod.partitions):
				sorted_device_mods.remove(mod)
				sorted_device_mods.insert(0, mod)
				break

		for mod in sorted_device_mods:
			not_pv_part_mods = [p for p in mod.partitions if p not in pvs]

			# partitions have to mounted in the right order on btrfs the mountpoint will
			# be empty as the actual subvolumes are getting mounted instead so we'll use
			# '/' just for sorting
			sorted_part_mods = sorted(not_pv_part_mods, key=lambda x: x.mountpoint or Path('/'))

			for part_mod in sorted_part_mods:
				if luks_handler := luks_handlers.get(part_mod):
					self._mount_luks_partition(part_mod, luks_handler)
				else:
					self._mount_partition(part_mod)

	def _mount_lvm_layout(self, luks_handlers: dict[PartitionModification | LvmVolume, Luks2] | None = None) -> None:
		if luks_handlers is None:
			luks_handlers = {}

		lvm_config = self._disk_config.lvm_config

		if not lvm_config:
			debug('No lvm config defined to be mounted')
			return

		debug('Mounting LVM layout')

		for vg in lvm_config.vol_groups:
			sorted_vol = sorted(vg.volumes, key=lambda x: x.mountpoint or Path('/'))

			for vol in sorted_vol:
				if luks_handler := luks_handlers.get(vol):
					self._mount_luks_volume(vol, luks_handler)
				else:
					self._mount_lvm_vol(vol)

	def _prepare_luks_partitions(
		self,
		partitions: list[PartitionModification],
	) -> dict[PartitionModification | LvmVolume, Luks2]:
		return {
			part_mod: unlock_luks2_dev(
				part_mod.dev_path,
				part_mod.mapper_name,
				self._disk_encryption.encryption_password,
			)
			for part_mod in partitions
			if part_mod.mapper_name and part_mod.dev_path
		}

	def _import_lvm(self) -> None:
		lvm_config = self._disk_config.lvm_config

		if not lvm_config:
			debug('No lvm config defined to be imported')
			return

		for vg in lvm_config.vol_groups:
			lvm_import_vg(vg)

			for vol in vg.volumes:
				lvm_vol_change(vol, True)

	def _prepare_luks_lvm(
		self,
		lvm_volumes: list[LvmVolume],
	) -> dict[PartitionModification | LvmVolume, Luks2]:
		return {
			vol: unlock_luks2_dev(
				vol.dev_path,
				vol.mapper_name,
				self._disk_encryption.encryption_password,
			)
			for vol in lvm_volumes
			if vol.mapper_name and vol.dev_path
		}

	# src/shared/dissect-image.c. FAT has no on-disk perms, hence the masks
	def _mount_partition(self, part_mod: PartitionModification) -> None:
		if not part_mod.dev_path:
			debug(f'Partition {part_mod.mountpoint or part_mod.fs_type} has no device path, skipping mount')
			return

		# subvolumes carry their own mountpoints and win over the partition's, which
		# a manual layout can still set: mounting that would put the install on the
		# top-level subvolume and leave every subvolume created but unused
		if part_mod.fs_type == FilesystemType.BTRFS and part_mod.btrfs_subvols:
			if self._has_mountable_subvols(part_mod.dev_path, part_mod.btrfs_subvols):
				self._mount_btrfs_subvol(
					part_mod.dev_path,
					part_mod.btrfs_subvols,
					part_mod.mount_options,
				)
		elif part_mod.mountpoint:
			target = self.target / part_mod.relative_mountpoint
			mount_fs = part_mod.fs_type.fs_type_mount if part_mod.fs_type else None
			options = harden_boot_options(part_mod, list(part_mod.mount_options))

			mount(part_mod.dev_path, target, mount_fs=mount_fs, options=options)
		elif part_mod.is_swap():
			swapon(part_mod.dev_path)

	def _mount_lvm_vol(self, volume: LvmVolume) -> None:
		if volume.fs_type != FilesystemType.BTRFS and volume.mountpoint and volume.dev_path:
			target = self.target / volume.relative_mountpoint
			mount(volume.dev_path, target, mount_fs=volume.fs_type.fs_type_mount, options=volume.mount_options)

		if volume.fs_type == FilesystemType.BTRFS and volume.dev_path and self._has_mountable_subvols(volume.dev_path, volume.btrfs_subvols):
			self._mount_btrfs_subvol(volume.dev_path, volume.btrfs_subvols, volume.mount_options)

	def _mount_luks_partition(self, part_mod: PartitionModification, luks_handler: Luks2) -> None:
		if not luks_handler.mapper_dev:
			return

		if part_mod.fs_type == FilesystemType.BTRFS and part_mod.btrfs_subvols:
			if self._has_mountable_subvols(luks_handler.mapper_dev, part_mod.btrfs_subvols):
				self._mount_btrfs_subvol(luks_handler.mapper_dev, part_mod.btrfs_subvols, part_mod.mount_options)
		elif part_mod.is_swap():
			swapon(luks_handler.mapper_dev)
			self._fstab_entries.append(f'{luks_handler.mapper_dev}\tnone\tswap\tdefaults\t0\t0')
		elif part_mod.mountpoint:
			target = self.target / part_mod.relative_mountpoint
			mount_fs = part_mod.fs_type.fs_type_mount if part_mod.fs_type else None
			# encrypted /boot (GRUB) needs the same hardening as a plain one
			options = harden_boot_options(part_mod, list(part_mod.mount_options))
			mount(luks_handler.mapper_dev, target, mount_fs=mount_fs, options=options)

	def _mount_luks_volume(self, volume: LvmVolume, luks_handler: Luks2) -> None:
		mapper = luks_handler.mapper_dev

		if volume.fs_type != FilesystemType.BTRFS and volume.mountpoint and mapper:
			target = self.target / volume.relative_mountpoint
			mount(mapper, target, mount_fs=volume.fs_type.fs_type_mount, options=volume.mount_options)

		if volume.fs_type == FilesystemType.BTRFS and mapper and self._has_mountable_subvols(mapper, volume.btrfs_subvols):
			self._mount_btrfs_subvol(mapper, volume.btrfs_subvols, volume.mount_options)

	def _has_mountable_subvols(self, dev_path: Path, subvolumes: list[SubvolumeModification]) -> bool:
		# only subvolumes with a mountpoint get mounted, and the partition must
		# not stand in for them: an empty set means nothing lands here
		if any(sv.mountpoint is not None for sv in subvolumes):
			return True

		warn(f'{dev_path}: no btrfs subvolume with a mountpoint, nothing mounted there')
		return False

	def _mount_btrfs_subvol(
		self,
		dev_path: Path,
		subvolumes: list[SubvolumeModification],
		mount_options: list[str] | None = None,
	) -> None:
		if mount_options is None:
			mount_options = []

		# Filter out subvolumes without mountpoints to avoid errors when sorting
		subvols_with_mountpoints = [sv for sv in subvolumes if sv.mountpoint is not None]
		for subvol in sorted(subvols_with_mountpoints, key=lambda x: x.relative_mountpoint):
			mountpoint = self.target / subvol.relative_mountpoint
			options = [*mount_options, f'subvol={subvol.name}']
			mount(dev_path, mountpoint, mount_fs='btrfs', options=options)
