from pathlib import Path

from archinstoo.lib.hardware import SysInfo
from archinstoo.lib.models.bootloader import Bootloader
from archinstoo.lib.models.device import (
	BDevice,
	DeviceModification,
	DiskLayoutConfiguration,
	DiskLayoutType,
	FilesystemType,
	LvmConfiguration,
	LvmLayoutType,
	LvmVolume,
	LvmVolumeGroup,
	ModificationStatus,
	PartitionFlag,
	PartitionModification,
	PartitionTable,
	PartitionType,
	SectorSize,
	Size,
	SubvolumeModification,
	Unit,
)
from archinstoo.lib.translationhandler import tr
from archinstoo.lib.tui.curses_menu import SelectMenu
from archinstoo.lib.tui.menu_item import MenuItem, MenuItemGroup
from archinstoo.lib.tui.types import Alignment, Orientation

from .selectors import select_main_filesystem_format, select_mount_options, select_partition_table


def _boot_partition(
	sector_size: SectorSize,
	using_gpt: bool,
	uefi: bool,
	bootloader: Bootloader | None = None,
	filesystem_type: FilesystemType = FilesystemType.EXT4,
	using_subvolumes: bool = False,
) -> list[PartitionModification]:
	partitions = []
	start = Size(1, Unit.MiB, sector_size)

	if uefi:
		# UEFI: ESP, mount at /efi for btrfs subvolumes so /boot stays in @
		mountpoint = Path('/efi') if using_subvolumes else Path('/boot')
		partitions.append(
			PartitionModification(
				status=ModificationStatus.CREATE,
				type=PartitionType.PRIMARY,
				start=start,
				length=Size(1, Unit.GiB, sector_size),
				mountpoint=mountpoint,
				fs_type=FilesystemType.FAT32,
				flags=[PartitionFlag.ESP],
			)
		)
	else:
		# BIOS+GPT: small ef02 partition for GRUB's core.img
		# Limine uses the MBR gap directly, so it doesn't need this
		if using_gpt and bootloader == Bootloader.Grub:
			partitions.append(
				PartitionModification(
					status=ModificationStatus.CREATE,
					type=PartitionType.PRIMARY,
					start=start,
					length=Size(1, Unit.MiB, sector_size),
					mountpoint=None,
					fs_type=None,
					flags=[PartitionFlag.BIOS_GRUB],
				)
			)
			start = Size(2, Unit.MiB, sector_size)

		# BIOS: /boot — GRUB can read the user's chosen fs, Limine only supports FAT
		boot_fs = FilesystemType.FAT32 if bootloader == Bootloader.Limine else filesystem_type
		partitions.append(
			PartitionModification(
				status=ModificationStatus.CREATE,
				type=PartitionType.PRIMARY,
				start=start,
				length=Size(1, Unit.GiB, sector_size),
				mountpoint=Path('/boot'),
				fs_type=boot_fs,
				flags=[PartitionFlag.BOOT],
			)
		)

	return partitions


def process_root_partition_size(total_size: Size, sector_size: SectorSize) -> Size:
	# root partition size processing
	total_device_size = total_size.convert(Unit.GiB)
	if total_device_size.value > 500:
		# maximum size
		return Size(value=50, unit=Unit.GiB, sector_size=sector_size)
	if total_device_size.value < 320:
		# minimum size
		return Size(value=32, unit=Unit.GiB, sector_size=sector_size)
	# 10% of total size
	length = total_device_size.value // 10
	return Size(value=length, unit=Unit.GiB, sector_size=sector_size)


def get_default_btrfs_subvols() -> list[SubvolumeModification]:
	# https://btrfs.wiki.kernel.org/index.php/FAQ
	# https://unix.stackexchange.com/questions/246976/btrfs-subvolume-uuid-clash
	# https://github.com/classy-giraffe/easy-arch/blob/main/easy-arch.sh
	return [
		SubvolumeModification(Path('@'), Path('/')),
		SubvolumeModification(Path('@home'), Path('/home')),
		SubvolumeModification(Path('@log'), Path('/var/log')),
		SubvolumeModification(Path('@pkg'), Path('/var/cache/pacman/pkg')),
	]


def suggest_single_disk_layout(
	device: BDevice,
	filesystem_type: FilesystemType | None = None,
	separate_home: bool | None = None,
	bootloader: Bootloader | None = None,
	advanced: bool = False,
) -> DeviceModification:
	if not filesystem_type:
		filesystem_type = select_main_filesystem_format(advanced=advanced)

	sector_size = device.device_info.sector_size
	total_size = device.device_info.total_size
	available_space = total_size
	min_size_to_allow_home_part = Size(64, Unit.GiB, sector_size)

	if filesystem_type == FilesystemType.BTRFS:
		prompt = tr('Would you like to use BTRFS subvolumes with a default structure?') + '\n'
		group = MenuItemGroup.yes_no()
		group.set_focus_by_value(MenuItem.yes().value)
		result = SelectMenu[bool](
			group,
			header=prompt,
			alignment=Alignment.CENTER,
			columns=2,
			orientation=Orientation.HORIZONTAL,
			allow_skip=False,
		).run()

		using_subvolumes = result.item() == MenuItem.yes()
		mount_options = select_mount_options()
	else:
		using_subvolumes = False
		mount_options = []

	uefi = SysInfo.has_uefi()
	partition_table = PartitionTable.GPT if uefi else select_partition_table()
	device_modification = DeviceModification(device, wipe=True, partition_table=partition_table)

	using_gpt = partition_table.is_gpt()

	if using_gpt:
		available_space = available_space.gpt_end()

	available_space = available_space.align()

	# Used for reference: https://wiki.archlinux.org/title/partitioning
	boot_partitions = _boot_partition(sector_size, using_gpt, uefi, bootloader, filesystem_type, using_subvolumes)
	for part in boot_partitions:
		device_modification.add_partition(part)

	if separate_home is False or using_subvolumes or total_size < min_size_to_allow_home_part:
		using_home_partition = False
	elif separate_home:
		using_home_partition = True
	else:
		prompt = tr('Would you like to create a separate partition for /home?') + '\n'
		group = MenuItemGroup.yes_no()
		group.set_focus_by_value(MenuItem.yes().value)
		result = SelectMenu(
			group,
			header=prompt,
			orientation=Orientation.HORIZONTAL,
			columns=2,
			alignment=Alignment.CENTER,
			allow_skip=False,
		).run()

		using_home_partition = result.item() == MenuItem.yes()

	# root partition starts after last boot partition
	last_boot = boot_partitions[-1]
	root_start = last_boot.start + last_boot.length

	# Set a size for / (/root)
	root_length = process_root_partition_size(total_size, sector_size) if using_home_partition else available_space - root_start

	root_partition = PartitionModification(
		status=ModificationStatus.CREATE,
		type=PartitionType.PRIMARY,
		start=root_start,
		length=root_length,
		mountpoint=Path('/') if not using_subvolumes else None,
		fs_type=filesystem_type,
		mount_options=mount_options,
	)

	device_modification.add_partition(root_partition)

	if using_subvolumes:
		root_partition.btrfs_subvols = get_default_btrfs_subvols()
	elif using_home_partition:
		# If we don't want to use subvolumes,
		# But we want to be able to reuse data between re-installs..
		# A second partition for /home would be nice if we have the space for it
		home_start = root_partition.start + root_partition.length
		home_length = available_space - home_start

		flags = []
		if using_gpt:
			flags.append(PartitionFlag.LINUX_HOME)

		home_partition = PartitionModification(
			status=ModificationStatus.CREATE,
			type=PartitionType.PRIMARY,
			start=home_start,
			length=home_length,
			mountpoint=Path('/home'),
			fs_type=filesystem_type,
			mount_options=mount_options,
			flags=flags,
		)
		device_modification.add_partition(home_partition)

	return device_modification


def suggest_lvm_layout(
	disk_config: DiskLayoutConfiguration,
	filesystem_type: FilesystemType | None = None,
	vg_grp_name: str = 'ArchinstooVg',
	advanced: bool = False,
) -> LvmConfiguration:
	if disk_config.config_type != DiskLayoutType.Default:
		raise ValueError('LVM suggested volumes are only available for default partitioning')

	using_subvolumes = False
	btrfs_subvols = []
	home_volume = True
	mount_options = []

	if not filesystem_type:
		filesystem_type = select_main_filesystem_format(advanced=advanced)

	if filesystem_type == FilesystemType.BTRFS:
		prompt = tr('Would you like to use BTRFS subvolumes with a default structure?') + '\n'
		group = MenuItemGroup.yes_no()
		group.set_focus_by_value(MenuItem.yes().value)

		result = SelectMenu[bool](
			group,
			header=prompt,
			search_enabled=False,
			allow_skip=False,
			orientation=Orientation.HORIZONTAL,
			columns=2,
			alignment=Alignment.CENTER,
		).run()

		using_subvolumes = MenuItem.yes() == result.item()
		mount_options = select_mount_options()

	if using_subvolumes:
		btrfs_subvols = get_default_btrfs_subvols()
		home_volume = False

	boot_part: PartitionModification | None = None
	other_part: list[PartitionModification] = []

	efi_part: PartitionModification | None = None

	for mod in disk_config.device_modifications:
		for part in mod.partitions:
			if part.is_boot():
				boot_part = part
			elif part.is_efi():
				efi_part = part
			else:
				other_part.append(part)

	if not boot_part:
		boot_part = efi_part

	if not boot_part:
		raise ValueError('Unable to find boot partition in partition modifications')

	total_vol_available = sum(
		[p.length for p in other_part],
		Size(0, Unit.B, SectorSize.default()),
	)
	root_vol_size = process_root_partition_size(total_vol_available, SectorSize.default())
	home_vol_size = total_vol_available - root_vol_size

	lvm_vol_group = LvmVolumeGroup(vg_grp_name, pvs=other_part)

	root_vol = LvmVolume(
		status=ModificationStatus.CREATE,
		name='root',
		fs_type=filesystem_type,
		length=root_vol_size,
		mountpoint=Path('/'),
		btrfs_subvols=btrfs_subvols,
		mount_options=mount_options,
	)

	lvm_vol_group.volumes.append(root_vol)

	if home_volume:
		home_vol = LvmVolume(
			status=ModificationStatus.CREATE,
			name='home',
			fs_type=filesystem_type,
			length=home_vol_size,
			mountpoint=Path('/home'),
		)

		lvm_vol_group.volumes.append(home_vol)

	return LvmConfiguration(LvmLayoutType.Default, [lvm_vol_group])


def get_default_partition_layout(
	device: BDevice,
	filesystem_type: FilesystemType | None = None,
	bootloader: Bootloader | None = None,
	advanced: bool = False,
) -> DeviceModification:
	return suggest_single_disk_layout(
		device,
		filesystem_type=filesystem_type,
		bootloader=bootloader,
		advanced=advanced,
	)
