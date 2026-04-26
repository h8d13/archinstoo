from archinstoo.lib.menu.menu_helper import MenuHelper
from archinstoo.lib.models.device import (
	BDevice,
	BtrfsMountOption,
	FilesystemType,
	PartitionTable,
	_DeviceInfo,
)
from archinstoo.lib.output import FormattedOutput
from archinstoo.lib.translationhandler import tr
from archinstoo.lib.tui.curses_menu import SelectMenu
from archinstoo.lib.tui.menu_item import MenuItem, MenuItemGroup
from archinstoo.lib.tui.result import ResultType
from archinstoo.lib.tui.types import Alignment, FrameProperties, Orientation, PreviewStyle

from .device_handler import DeviceHandler


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
		MenuItem('btrfs', value=FilesystemType.BTRFS),
		MenuItem('ext4', value=FilesystemType.EXT4),
		MenuItem('xfs', value=FilesystemType.XFS),
		MenuItem('f2fs', value=FilesystemType.F2FS),
	]

	if advanced:
		items.append(MenuItem('bcachefs', value=FilesystemType.BCACHEFS))
		items.append(MenuItem('ntfs', value=FilesystemType.NTFS))

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

	# noatime is always included for btrfs to avoid unnecessary metadata
	# writes due to atime updates interacting poorly with CoW and snapshots
	# https://github.com/archlinux/archinstall/issues/582
	default_options = [BtrfsMountOption.noatime.value]

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
			return default_options
		case ResultType.Selection:
			return default_options + [result.get_value()]
		case _:
			raise ValueError('Unhandled result type')
