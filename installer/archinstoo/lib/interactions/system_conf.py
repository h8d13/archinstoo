from typing import assert_never

from archinstoo.lib.models.firmware import (
	FIRMWARE_OPTDEPS,
	FirmwareConfiguration,
	FirmwareType,
	FirmwareVendor,
)
from archinstoo.lib.tui.curses_menu import SelectMenu
from archinstoo.lib.tui.menu_item import MenuItem, MenuItemGroup
from archinstoo.lib.tui.result import ResultType
from archinstoo.lib.tui.types import Alignment, FrameProperties


def select_firmware(
	preset: FirmwareConfiguration | None = None,
) -> FirmwareConfiguration:
	# Host-dependent (MINIMAL in a VM), so it cannot be a signature default
	default = FirmwareConfiguration.default()
	preset = preset or default

	header = (
		'Full installs the linux-firmware meta package, plus picked optional '
		'firmware.\n'
	)
	header += 'Minimal skips firmware entirely (safe for most VMs using virtio).\n'
	header += 'Vendor lets you pick only the firmware subpackages you need.\n'

	type_items = [MenuItem(t.value, value=t) for t in FirmwareType]
	type_group = MenuItemGroup(type_items, sort_items=False)
	type_group.set_default_by_value(default.firmware_type)
	type_group.set_focus_by_value(preset.firmware_type)

	result = SelectMenu[FirmwareType](
		type_group,
		header=header,
		allow_skip=True,
		alignment=Alignment.CENTER,
		frame=FrameProperties.min('Firmware'),
	).run()

	match result.type_:
		case ResultType.Skip:
			return preset
		case ResultType.Reset:
			return default
		case ResultType.Selection:
			firmware_type = result.get_value()
		case _:
			assert_never(result.type_)

	if firmware_type == FirmwareType.MINIMAL:
		return FirmwareConfiguration(firmware_type=firmware_type)

	if firmware_type == FirmwareType.FULL:
		# linux-firmware leaves its optdeps out, so they are opt-in here
		choices = sorted(FIRMWARE_OPTDEPS)
		title = 'Optional firmware'
		vendor_header = (
			'Select optional firmware (none are pulled in by '
			'linux-firmware):'
		)
	else:
		choices = list(FirmwareVendor)
		title = 'Firmware vendors'
		vendor_header = 'Select firmware subpackages:'

	# a pick saved under the other type may hold names this list lacks
	kept = [v for v in preset.vendors if v in choices]
	vendor_group = MenuItemGroup(
		[MenuItem(v.value, value=v) for v in choices], sort_items=True
	)
	vendor_group.set_selected_by_value(kept)

	vendor_result = SelectMenu[FirmwareVendor](
		vendor_group,
		header=vendor_header + '\n',
		allow_skip=True,
		allow_reset=True,
		alignment=Alignment.CENTER,
		frame=FrameProperties.min(title),
		multi=True,
	).run()

	match vendor_result.type_:
		case ResultType.Skip:
			vendors = kept
		case ResultType.Selection:
			vendors = vendor_result.get_values()
		case ResultType.Reset:
			vendors = []
		case _:
			assert_never(vendor_result.type_)

	return FirmwareConfiguration(firmware_type=firmware_type, vendors=vendors)
