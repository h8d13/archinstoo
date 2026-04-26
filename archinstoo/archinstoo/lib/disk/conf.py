from archinstoo.lib.models.bootloader import Bootloader
from archinstoo.lib.models.device import (
	BDevice,
	DeviceModification,
	DiskLayoutConfiguration,
	DiskLayoutType,
	LvmConfiguration,
	LvmLayoutType,
)
from archinstoo.lib.translationhandler import tr
from archinstoo.lib.tui.curses_menu import SelectMenu
from archinstoo.lib.tui.menu_item import MenuItem, MenuItemGroup
from archinstoo.lib.tui.prompts import prompt_dir
from archinstoo.lib.tui.result import ResultType
from archinstoo.lib.tui.types import Alignment, FrameProperties

from .device_handler import DeviceHandler
from .layouts import get_default_partition_layout, suggest_lvm_layout
from .partitioning_menu import manual_partitioning
from .selectors import select_device


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

	items = [
		MenuItem(manual_mode, value=manual_mode),
		MenuItem(default_layout, value=default_layout),
		MenuItem(pre_mount_mode, value=pre_mount_mode),
	]
	group = MenuItemGroup(items, sort_items=False)

	if preset:
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
