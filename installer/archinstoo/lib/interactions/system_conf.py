from typing import assert_never

from archinstoo.lib.models.firmware import FIRMWARE_OPTDEPS, FirmwareConfiguration, FirmwareType, FirmwareVendor
from archinstoo.lib.models.kernel import DEFAULT_KERNEL, Kernel, kernel_names_error
from archinstoo.lib.models.swap import SwapConfiguration, ZramAlgorithm
from archinstoo.lib.tui.curses_menu import SelectMenu
from archinstoo.lib.tui.menu_item import MenuItem, MenuItemGroup
from archinstoo.lib.tui.prompts import prompt_choice, prompt_text, prompt_yes_no
from archinstoo.lib.tui.result import ResultType
from archinstoo.lib.tui.types import Alignment, FrameProperties

# menu entry that opens the name prompt, no package is named ''
_TYPE_KERNEL = ''


def select_kernel(preset: list[str] | None = None) -> list[str]:
	# stock kernels, then names typed on an earlier visit so they stay
	# tickable, then the escape hatch for board kernels (linux-rpi5)
	preset = preset or []
	stock = [k.value for k in Kernel]
	typed = sorted(k for k in preset if k not in stock)

	items = [MenuItem(k, value=k) for k in sorted(stock) + typed]
	items.append(MenuItem('Custom (type a name)', value=_TYPE_KERNEL))
	group = MenuItemGroup(items)
	group.set_selected_by_value(preset)
	group.set_default_by_value(DEFAULT_KERNEL.value)
	group.set_focus_by_value(DEFAULT_KERNEL.value)

	result = SelectMenu[str](
		group,
		allow_skip=True,
		allow_reset=True,
		alignment=Alignment.CENTER,
		frame=FrameProperties.min('Kernel'),
		multi=True,
	).run()

	match result.type_:
		case ResultType.Skip:
			return preset
		case ResultType.Reset:
			return []
		case ResultType.Selection:
			picked = result.get_values()
		case _:
			assert_never(result.type_)

	if _TYPE_KERNEL not in picked:
		return picked

	header = 'Kernel package names, space separated (e.g. linux-rpi5)' + '\n'
	names = prompt_text('Custom kernels', header, validator=kernel_names_error)
	kept = [k for k in picked if k != _TYPE_KERNEL]
	# a skipped prompt keeps the ticked kernels, dict.fromkeys drops repeats
	return list(dict.fromkeys(kept + (names or '').split()))


def select_swap(preset: SwapConfiguration | None = None) -> SwapConfiguration:
	if preset is None:
		preset = SwapConfiguration()

	zram = prompt_yes_no('Would you like to use swap on zram?' + '\n', preset.zram, default=True)
	if zram is None:
		return preset

	algo = preset.algorithm
	recomp_algo: ZramAlgorithm | None = None
	if zram:
		algo_group = MenuItemGroup.from_enum(ZramAlgorithm)
		algo = (
			prompt_choice(algo_group, preset.algorithm, header='Select zram compression algorithm:' + '\n', default=ZramAlgorithm.Default)
			or preset.algorithm
		)

		# Ask for idle recompression algorithm (only if a specific primary algo was chosen)
		if algo != ZramAlgorithm.Default:
			recomp_algo = _select_recomp_algorithm(preset.recomp_algorithm)

	hib_prompt = 'Enable hibernation? Creates a disk swap file sized to RAM.' + '\n'
	hibernation = prompt_yes_no(hib_prompt, preset.hibernation, default=False)
	if hibernation is None:
		hibernation = preset.hibernation

	return SwapConfiguration(
		zram=zram,
		algorithm=algo,
		recomp_algorithm=recomp_algo,
		hibernation=hibernation,
		size_gib=preset.size_gib,
	)


def select_firmware(preset: FirmwareConfiguration | None = None) -> FirmwareConfiguration:
	# Host-dependent (MINIMAL in a VM), so it cannot be a signature default
	default = FirmwareConfiguration.default()
	preset = preset or default

	header = 'Full installs the linux-firmware meta package, plus picked optional firmware.' + '\n'
	header += 'Minimal skips firmware entirely (safe for most VMs using virtio).' + '\n'
	header += 'Vendor lets you pick only the firmware subpackages you need.' + '\n'

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
		vendor_header = 'Select optional firmware (none are pulled in by linux-firmware):'
	else:
		choices = list(FirmwareVendor)
		title = 'Firmware vendors'
		vendor_header = 'Select firmware subpackages:'

	# a pick saved under the other type may hold names this list lacks
	kept = [v for v in preset.vendors if v in choices]
	vendor_group = MenuItemGroup([MenuItem(v.value, value=v) for v in choices], sort_items=True)
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


def _select_recomp_algorithm(preset: ZramAlgorithm | None) -> ZramAlgorithm | None:
	prompt = 'Select idle recompression algorithm (skip for none):' + '\n'

	# Exclude Default since recompression needs a specific algorithm
	recomp_items = [MenuItem(algo.value, value=algo) for algo in ZramAlgorithm if algo != ZramAlgorithm.Default]
	return prompt_choice(recomp_items, preset, header=prompt)
