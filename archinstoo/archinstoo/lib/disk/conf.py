from pathlib import Path

from archinstoo.lib.hardware import SysInfo
from archinstoo.lib.menu.menu_helper import MenuHelper
from archinstoo.lib.models.bootloader import Bootloader
from archinstoo.lib.models.device import (
	DEFAULT_ZFS_DATASETS,
	BDevice,
	BtrfsMountOption,
	DeviceModification,
	DiskLayoutConfiguration,
	DiskLayoutType,
	FilesystemType,
	LvmConfiguration,
	LvmLayoutType,
	LvmVolume,
	LvmVolumeGroup,
	LvmVolumeStatus,
	ModificationStatus,
	PartitionFlag,
	PartitionModification,
	PartitionTable,
	PartitionType,
	SectorSize,
	Size,
	SubvolumeModification,
	Unit,
	ZfsConfiguration,
	ZfsLayoutType,
	ZfsPool,
	_DeviceInfo,
)
from archinstoo.lib.output import FormattedOutput
from archinstoo.lib.translationhandler import tr
from archinstoo.lib.tui.curses_menu import SelectMenu
from archinstoo.lib.tui.menu_item import MenuItem, MenuItemGroup
from archinstoo.lib.tui.prompts import prompt_dir
from archinstoo.lib.tui.result import ResultType
from archinstoo.lib.tui.types import Alignment, FrameProperties, Orientation, PreviewStyle

from .device_handler import DeviceHandler
from .partitioning_menu import manual_partitioning


def select_device(
	preset: BDevice | None = None,
	device_handler: DeviceHandler | None = None,
) -> BDevice | None:
	handler = device_handler or DeviceHandler()

	def _preview_device_selection(item: MenuItem) -> str | None:
		device = item.get_value()
		dev = handler.get_device(device.path)

		if dev and dev.partition_infos:
			return FormattedOutput.as_table(dev.partition_infos)
		return None

	devices = handler.devices
	options = [d.device_info for d in devices]

	group = MenuHelper(options).create_menu_group()

	if preset:
		group.set_selected_by_value([preset.device_info])

	group.set_preview_for_all(_preview_device_selection)

	result = SelectMenu[_DeviceInfo](
		group,
		alignment=Alignment.CENTER,
		search_enabled=False,
		preview_style=PreviewStyle.BOTTOM,
		preview_size='auto',
		preview_frame=FrameProperties.max('Partitions'),
		allow_skip=True,
	).run()

	match result.type_:
		case ResultType.Reset:
			return None
		case ResultType.Skip:
			return preset
		case ResultType.Selection:
			selected_device_info = result.get_value()

			for device in devices:
				if device.device_info == selected_device_info:
					return device

			return None


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


def _manual_partitioning(
	preset: DeviceModification | None,
	device: BDevice,
	device_handler: DeviceHandler | None = None,
	advanced: bool = False,
) -> DeviceModification | None:
	handler = device_handler or DeviceHandler()

	if not preset:
		preset = DeviceModification(device, wipe=False)

	return manual_partitioning(preset, handler.partition_table, advanced=advanced)


def select_disk_config(
	preset: DiskLayoutConfiguration | None = None,
	device_handler: DeviceHandler | None = None,
	bootloader: Bootloader | None = None,
	advanced: bool = False,
) -> DiskLayoutConfiguration | None:
	handler = device_handler or DeviceHandler()

	# if manual mode already configured, go directly to partition detail screen
	if preset and preset.config_type == DiskLayoutType.Manual and preset.device_modifications:
		preset_mod = preset.device_modifications[0]
		if (manual_modification := _manual_partitioning(preset_mod, preset_mod.device, handler, advanced=advanced)) is not None:
			return DiskLayoutConfiguration(
				config_type=DiskLayoutType.Manual,
				device_modifications=[manual_modification],
			)
		return None

	default_layout = DiskLayoutType.Default.display_msg()
	manual_mode = DiskLayoutType.Manual.display_msg()
	pre_mount_mode = DiskLayoutType.Pre_mount.display_msg()
	zfs_mode = 'ZFS layout'

	items = [
		MenuItem(manual_mode, value=manual_mode),
		MenuItem(default_layout, value=default_layout),
		MenuItem(pre_mount_mode, value=pre_mount_mode),
	]

	if advanced:
		items.append(MenuItem(zfs_mode, value=zfs_mode))

	group = MenuItemGroup(items, sort_items=False)

	if preset:
		if preset.zfs_config:
			group.set_selected_by_value(zfs_mode)
		else:
			group.set_selected_by_value(preset.config_type.display_msg())

	result = SelectMenu[str](
		group,
		allow_skip=True,
		alignment=Alignment.CENTER,
		frame=FrameProperties.min(tr('Disk configuration type')),
		allow_reset=True,
	).run()

	match result.type_:
		case ResultType.Skip:
			return preset
		case ResultType.Reset:
			return None
		case ResultType.Selection:
			selection = result.get_value()

			if selection == pre_mount_mode:
				output = 'You will use whatever drive-setup is mounted at the specified directory\n'
				output += "WARNING: Archinstoo won't check the suitability of this setup\n"

				path = prompt_dir(tr('Root mount directory'), output, allow_skip=True)

				if path is None:
					return None

				mods = handler.detect_pre_mounted_mods(path)

				return DiskLayoutConfiguration(
					config_type=DiskLayoutType.Pre_mount,
					device_modifications=mods,
					mountpoint=path,
				)

			if selection == zfs_mode:
				return suggest_zfs_layout(handler)

			preset_device = preset.device_modifications[0].device if preset and preset.device_modifications else None
			device = select_device(preset_device, device_handler=handler)

			if not device:
				return None

			if result.get_value() == default_layout:
				modification = get_default_partition_layout(device, bootloader=bootloader, advanced=advanced)
				return DiskLayoutConfiguration(
					config_type=DiskLayoutType.Default,
					device_modifications=[modification],
				)
			if result.get_value() == manual_mode and (manual_modification := _manual_partitioning(None, device, advanced=advanced)) is not None:
				return DiskLayoutConfiguration(
					config_type=DiskLayoutType.Manual,
					device_modifications=[manual_modification],
				)

	return None


def select_lvm_config(
	disk_config: DiskLayoutConfiguration,
	preset: LvmConfiguration | None = None,
	advanced: bool = False,
) -> LvmConfiguration | None:
	preset_value = preset.config_type.display_msg() if preset else None
	default_mode = LvmLayoutType.Default.display_msg()

	items = [MenuItem(default_mode, value=default_mode)]
	group = MenuItemGroup(items)
	group.set_focus_by_value(preset_value)

	result = SelectMenu[str](
		group,
		allow_reset=True,
		allow_skip=True,
		frame=FrameProperties.min(tr('LVM configuration type')),
		alignment=Alignment.CENTER,
	).run()

	match result.type_:
		case ResultType.Skip:
			return preset
		case ResultType.Reset:
			return None
		case ResultType.Selection:
			if result.get_value() == default_mode:
				return suggest_lvm_layout(disk_config, advanced=advanced)

	return None


def _boot_partition(
	sector_size: SectorSize,
	using_gpt: bool,
	uefi: bool,
	bootloader: Bootloader | None = None,
	filesystem_type: FilesystemType = FilesystemType.Ext4,
	using_subvolumes: bool = False,
) -> list[PartitionModification]:
	partitions = []
	start = Size(1, Unit.MiB, sector_size)

	if uefi:
		# UEFI: ESP, mount at /efi for btrfs subvolumes so /boot stays in @
		mountpoint = Path('/efi') if using_subvolumes else Path('/boot')
		partitions.append(
			PartitionModification(
				status=ModificationStatus.Create,
				type=PartitionType.Primary,
				start=start,
				length=Size(1, Unit.GiB, sector_size),
				mountpoint=mountpoint,
				fs_type=FilesystemType.Fat32,
				flags=[PartitionFlag.ESP],
			)
		)
	else:
		# BIOS+GPT: small ef02 partition for GRUB's core.img
		# Limine uses the MBR gap directly, so it doesn't need this
		if using_gpt and bootloader == Bootloader.Grub:
			partitions.append(
				PartitionModification(
					status=ModificationStatus.Create,
					type=PartitionType.Primary,
					start=start,
					length=Size(1, Unit.MiB, sector_size),
					mountpoint=None,
					fs_type=None,
					flags=[PartitionFlag.BIOS_GRUB],
				)
			)
			start = Size(2, Unit.MiB, sector_size)

		# BIOS: /boot — GRUB can read the user's chosen fs, Limine only supports FAT
		boot_fs = FilesystemType.Fat32 if bootloader == Bootloader.Limine else filesystem_type
		partitions.append(
			PartitionModification(
				status=ModificationStatus.Create,
				type=PartitionType.Primary,
				start=start,
				length=Size(1, Unit.GiB, sector_size),
				mountpoint=Path('/boot'),
				fs_type=boot_fs,
				flags=[PartitionFlag.BOOT],
			)
		)

	return partitions


def select_partition_table() -> PartitionTable:
	default = PartitionTable.default()
	items = [
		MenuItem('GPT', value=PartitionTable.GPT),
		MenuItem('MBR', value=PartitionTable.MBR),
	]
	group = MenuItemGroup(items, sort_items=False)
	group.set_focus_by_value(default)

	result = SelectMenu[PartitionTable](
		group,
		alignment=Alignment.CENTER,
		frame=FrameProperties.min(tr('Partition table')),
		allow_skip=False,
	).run()

	match result.type_:
		case ResultType.Selection:
			return result.get_value()
		case _:
			raise ValueError('Unhandled result type')


def select_main_filesystem_format(advanced: bool = False) -> FilesystemType:
	items = [
		MenuItem('btrfs', value=FilesystemType.Btrfs),
		MenuItem('ext4', value=FilesystemType.Ext4),
		MenuItem('xfs', value=FilesystemType.Xfs),
		MenuItem('f2fs', value=FilesystemType.F2fs),
	]

	if advanced:
		items.append(MenuItem('bcachefs', value=FilesystemType.Bcachefs))
		items.append(MenuItem('ntfs', value=FilesystemType.Ntfs))

	group = MenuItemGroup(items, sort_items=False)
	result = SelectMenu[FilesystemType](
		group,
		alignment=Alignment.CENTER,
		frame=FrameProperties.min('Filesystem'),
		allow_skip=False,
	).run()

	match result.type_:
		case ResultType.Selection:
			return result.get_value()
		case _:
			raise ValueError('Unhandled result type')


def select_mount_options() -> list[str]:
	prompt = tr('Would you like to use compression or disable CoW?') + '\n'
	compression = tr('Use compression')
	disable_cow = tr('Disable Copy-on-Write')

	items = [
		MenuItem(compression, value=BtrfsMountOption.compress.value),
		MenuItem(disable_cow, value=BtrfsMountOption.nodatacow.value),
	]
	group = MenuItemGroup(items, sort_items=False)
	result = SelectMenu[str](
		group,
		header=prompt,
		alignment=Alignment.CENTER,
		columns=2,
		orientation=Orientation.HORIZONTAL,
		search_enabled=False,
		allow_skip=True,
	).run()

	match result.type_:
		case ResultType.Skip:
			return []
		case ResultType.Selection:
			return [result.get_value()]
		case _:
			raise ValueError('Unhandled result type')


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

	if filesystem_type == FilesystemType.Btrfs:
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
		status=ModificationStatus.Create,
		type=PartitionType.Primary,
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
			status=ModificationStatus.Create,
			type=PartitionType.Primary,
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

	if filesystem_type == FilesystemType.Btrfs:
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
		status=LvmVolumeStatus.Create,
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
			status=LvmVolumeStatus.Create,
			name='home',
			fs_type=filesystem_type,
			length=home_vol_size,
			mountpoint=Path('/home'),
		)

		lvm_vol_group.volumes.append(home_vol)

	return LvmConfiguration(LvmLayoutType.Default, [lvm_vol_group])


def suggest_zfs_layout(
	device_handler: DeviceHandler | None = None,
	pool_name: str = 'zpool',
	dataset_prefix: str = 'archinstoo',
) -> DiskLayoutConfiguration | None:
	"""Create a default ZFS layout: ESP + one large Solaris Root partition."""
	handler = device_handler or DeviceHandler()

	device = select_device(device_handler=handler)
	if not device:
		return None

	sector_size = device.device_info.sector_size
	total_size = device.device_info.total_size
	available_space = total_size

	uefi = SysInfo.has_uefi()
	if not uefi:
		raise ValueError('ZFS requires UEFI boot (for ZFSBootMenu)')

	partition_table = PartitionTable.GPT
	device_modification = DeviceModification(device, wipe=True, partition_table=partition_table)
	available_space = available_space.gpt_end().align()

	# ESP partition (1 GiB)
	start = Size(1, Unit.MiB, sector_size)
	esp_partition = PartitionModification(
		status=ModificationStatus.Create,
		type=PartitionType.Primary,
		start=start,
		length=Size(1, Unit.GiB, sector_size),
		mountpoint=Path('/boot'),
		fs_type=FilesystemType.Fat32,
		flags=[PartitionFlag.ESP],
	)
	device_modification.add_partition(esp_partition)

	# ZFS partition (remaining space, no filesystem — ZFS handles it)
	zfs_start = esp_partition.start + esp_partition.length
	zfs_length = available_space - zfs_start

	zfs_partition = PartitionModification(
		status=ModificationStatus.Create,
		type=PartitionType.Primary,
		start=zfs_start,
		length=zfs_length,
		mountpoint=None,
		fs_type=None,
	)
	device_modification.add_partition(zfs_partition)

	# Create ZFS configuration
	zfs_pool = ZfsPool(
		name=pool_name,
		pvs=[zfs_partition],
		dataset_prefix=dataset_prefix,
		datasets=list(DEFAULT_ZFS_DATASETS),
		compression='lz4',
		mountpoint=Path('/mnt'),
	)

	zfs_config = ZfsConfiguration(
		config_type=ZfsLayoutType.Default,
		pool=zfs_pool,
	)

	return DiskLayoutConfiguration(
		config_type=DiskLayoutType.Default,
		device_modifications=[device_modification],
		zfs_config=zfs_config,
	)
