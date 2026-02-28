from typing import assert_never

from archinstoo.default_profiles.profile import Profile
from archinstoo.lib.hardware import GfxDriver, SysInfo
from archinstoo.lib.models.application import ZramAlgorithm, ZramConfiguration
from archinstoo.lib.translationhandler import tr
from archinstoo.lib.tui.curses_menu import SelectMenu
from archinstoo.lib.tui.menu_item import MenuItem, MenuItemGroup
from archinstoo.lib.tui.result import ResultType
from archinstoo.lib.tui.types import Alignment, FrameProperties, FrameStyle, Orientation, PreviewStyle


def select_kernel(preset: list[str] = []) -> list[str]:
	"""
	Asks the user to select a kernel for system.

	:return: The string as a selected kernel
	:rtype: string
	"""
	kernels = ['linux', 'linux-lts', 'linux-zen', 'linux-hardened']
	default_kernel = 'linux'

	items = [MenuItem(k, value=k) for k in kernels]

	group = MenuItemGroup(items, sort_items=True)
	group.set_default_by_value(default_kernel)
	group.set_focus_by_value(default_kernel)
	group.set_selected_by_value(preset)

	result = SelectMenu[str](
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
			return result.get_values()


def select_driver(
	options: list[GfxDriver] = [],
	preset: GfxDriver | None = None,
	profile: Profile | None = None,
	kernels: list[str] | None = None,
) -> GfxDriver | None:
	"""
	Somewhat convoluted function, whose job is simple.
	Select a graphics driver from a pre-defined set of popular options.

	This comment was stupid so I removed it. A profile should plain dictate
	What it needs to run and be in minimal functional state.
	"""
	if not options:
		if SysInfo.arch() != 'x86_64':
			# On ARM only mesa-based drivers are available
			options = [GfxDriver.MesaOpenSource]
		else:
			options = list(GfxDriver)

	servers = profile.display_servers() if profile else None

	def preview_driver(x: MenuItem, k: list[str] | None = kernels) -> str | None:
		if x.value is None:
			return None
		driver: GfxDriver = x.value
		return driver.packages_text(servers, k)

	items = [MenuItem(o.value, value=o, preview_action=preview_driver) for o in options]
	group = MenuItemGroup(items, sort_items=True)
	if GfxDriver.MesaOpenSource in options and (SysInfo.is_vm() or SysInfo.arch() != 'x86_64'):
		default_driver = GfxDriver.MesaOpenSource
	elif GfxDriver.AllOpenSource in options:
		default_driver = GfxDriver.AllOpenSource
	else:
		default_driver = options[0]
	group.set_default_by_value(default_driver)

	if preset is not None:
		group.set_focus_by_value(preset)

	header = ''
	if SysInfo.is_vm():
		header += tr('VM detected: use VM (software rendering) or VM (virtio-gpu) options.\n')
	if SysInfo.has_amd_graphics():
		header += tr('AMD detected: use All open-source, AMD / ATI, or Mesa (open-source) options.\n')
	if SysInfo.has_intel_graphics():
		header += tr('Intel detected: use All open-source, Intel (open-source), or Mesa (open-source) options.\n')
	if SysInfo.has_nvidia_graphics():
		header += tr('Nvidia detected: for Turing+ use open-kernel, otherwise use AUR for legacy drivers.\n')

	result = SelectMenu[GfxDriver](
		group,
		header=header,
		allow_skip=True,
		allow_reset=True,
		preview_size='auto',
		preview_style=PreviewStyle.BOTTOM,
		preview_frame=FrameProperties(tr('Info'), h_frame_style=FrameStyle.MIN),
	).run()

	match result.type_:
		case ResultType.Skip:
			return preset
		case ResultType.Reset:
			return None
		case ResultType.Selection:
			return result.get_value()


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


def _select_recomp_algorithm(preset: ZramAlgorithm | None) -> ZramAlgorithm | None:
	prompt = tr('Select idle recompression algorithm (skip for none):') + '\n'

	# Exclude Default since recompression needs a specific algorithm
	recomp_items = [
		MenuItem(algo.value, value=algo)
		for algo in ZramAlgorithm
		if algo != ZramAlgorithm.Default
	]
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
