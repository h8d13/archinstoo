from typing import assert_never

from archinstoo.lib.models.application import DEFAULT_KERNEL, Kernel, ZramAlgorithm, ZramConfiguration
from archinstoo.lib.models.firmware import FirmwareConfiguration, FirmwareType, FirmwareVendor
from archinstoo.lib.translationhandler import tr
from archinstoo.lib.tui.curses_menu import SelectMenu
from archinstoo.lib.tui.menu_item import MenuItem, MenuItemGroup
from archinstoo.lib.tui.result import ResultType
from archinstoo.lib.tui.types import Alignment, FrameProperties, Orientation


def select_kernel(preset: list[str] = []) -> list[str]:
	"""
	Asks the user to select a kernel for system.

	:return: The string as a selected kernel
	:rtype: string
	"""
	preset_kernels = [Kernel(p) for p in preset if p in Kernel._value2member_map_]

	group = MenuItemGroup.from_enum(Kernel, sort_items=True, preset=preset_kernels)
	group.set_default_by_value(DEFAULT_KERNEL)
	group.set_focus_by_value(DEFAULT_KERNEL)

	result = SelectMenu[Kernel](
		group,
		allow_skip=True,
		allow_reset=True,
		alignment=Alignment.CENTER,
		frame=FrameProperties.min(tr('Kernel')),
		multi=True,
	).run()

	match result.type_:
		case ResultType.Skip:
			return preset
		case ResultType.Reset:
			return []
		case ResultType.Selection:
			return [k.value for k in result.get_values()]


def select_swap(preset: ZramConfiguration = ZramConfiguration(enabled=True)) -> ZramConfiguration:
	prompt = tr('Would you like to use swap on zram?') + '\n'

	group = MenuItemGroup.yes_no()
	group.set_default_by_value(True)
	group.set_focus_by_value(preset.enabled)

	result = SelectMenu[bool](
		group,
		header=prompt,
		columns=2,
		orientation=Orientation.HORIZONTAL,
		alignment=Alignment.CENTER,
		allow_skip=True,
	).run()

	match result.type_:
		case ResultType.Skip:
			return preset
		case ResultType.Selection:
			enabled = result.item() == MenuItem.yes()
			if not enabled:
				return ZramConfiguration(enabled=False)

			# Ask for compression algorithm
			algo_group = MenuItemGroup.from_enum(ZramAlgorithm, sort_items=False)
			algo_group.set_default_by_value(ZramAlgorithm.Default)
			algo_group.set_focus_by_value(preset.algorithm)

			algo_result = SelectMenu[ZramAlgorithm](
				algo_group,
				header=tr('Select zram compression algorithm:') + '\n',
				alignment=Alignment.CENTER,
				allow_skip=True,
			).run()

			match algo_result.type_:
				case ResultType.Skip:
					algo = preset.algorithm
				case ResultType.Selection:
					algo = algo_result.get_value()
				case ResultType.Reset:
					raise ValueError('Unhandled result type')
				case _:
					assert_never(algo_result.type_)

			# Ask for idle recompression algorithm (only if a specific primary algo was chosen)
			recomp_algo: ZramAlgorithm | None = None
			if algo != ZramAlgorithm.Default:
				recomp_algo = _select_recomp_algorithm(preset.recomp_algorithm)

			return ZramConfiguration(enabled=True, algorithm=algo, recomp_algorithm=recomp_algo)
		case ResultType.Reset:
			raise ValueError('Unhandled result type')


def select_firmware(preset: FirmwareConfiguration = FirmwareConfiguration()) -> FirmwareConfiguration:
	header = tr('Full installs the linux-firmware meta package (~600 MB).') + '\n'
	header += tr('Minimal skips firmware entirely (safe for most VMs using virtio).') + '\n'
	header += tr('Vendor lets you pick only the firmware subpackages you need.') + '\n'

	type_items = [MenuItem(t.value, value=t) for t in FirmwareType]
	type_group = MenuItemGroup(type_items, sort_items=False)
	type_group.set_default_by_value(FirmwareType.FULL)
	type_group.set_focus_by_value(preset.firmware_type)

	result = SelectMenu[FirmwareType](
		type_group,
		header=header,
		allow_skip=True,
		alignment=Alignment.CENTER,
		frame=FrameProperties.min(tr('Firmware')),
	).run()

	match result.type_:
		case ResultType.Skip:
			return preset
		case ResultType.Reset:
			return FirmwareConfiguration()
		case ResultType.Selection:
			firmware_type = result.get_value()
		case _:
			assert_never(result.type_)

	if firmware_type != FirmwareType.VENDOR:
		return FirmwareConfiguration(firmware_type=firmware_type)

	vendor_items = [MenuItem(v.value, value=v) for v in FirmwareVendor]
	vendor_group = MenuItemGroup(vendor_items, sort_items=True)
	vendor_group.set_selected_by_value(preset.vendors)

	vendor_result = SelectMenu[FirmwareVendor](
		vendor_group,
		header=tr('Select firmware subpackages:') + '\n',
		allow_skip=True,
		alignment=Alignment.CENTER,
		frame=FrameProperties.min(tr('Firmware vendors')),
		multi=True,
	).run()

	match vendor_result.type_:
		case ResultType.Skip:
			vendors = preset.vendors
		case ResultType.Selection:
			vendors = vendor_result.get_values()
		case ResultType.Reset:
			vendors = []
		case _:
			assert_never(vendor_result.type_)

	return FirmwareConfiguration(firmware_type=FirmwareType.VENDOR, vendors=vendors)


def _select_recomp_algorithm(preset: ZramAlgorithm | None) -> ZramAlgorithm | None:
	prompt = tr('Select idle recompression algorithm (skip for none):') + '\n'

	# Exclude Default since recompression needs a specific algorithm
	recomp_items = [MenuItem(algo.value, value=algo) for algo in ZramAlgorithm if algo != ZramAlgorithm.Default]
	recomp_group = MenuItemGroup(recomp_items, sort_items=False)

	if preset:
		recomp_group.set_focus_by_value(preset)

	recomp_result = SelectMenu[ZramAlgorithm](
		recomp_group,
		header=prompt,
		alignment=Alignment.CENTER,
		allow_skip=True,
	).run()

	match recomp_result.type_:
		case ResultType.Skip:
			return preset
		case ResultType.Selection:
			return recomp_result.get_value()
		case ResultType.Reset:
			raise ValueError('Unhandled result type')
		case _:
			assert_never(recomp_result.type_)
