from typing import assert_never

from archinstall.default_profiles.profile import Profile
from archinstall.lib.hardware import GfxDriver, SysInfo
from archinstall.lib.models.application import ZramAlgorithm, ZramConfiguration
from archinstall.lib.translationhandler import tr
from archinstall.lib.tui.curses_menu import SelectMenu
from archinstall.lib.tui.menu_item import MenuItem, MenuItemGroup
from archinstall.lib.tui.result import ResultType
from archinstall.lib.tui.types import Alignment, FrameProperties, FrameStyle, Orientation, PreviewStyle


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
	if SysInfo.has_amd_graphics():
		header += tr('For the best compat with your AMD hardware, you may want to use either the all open-source or AMD / ATI options.') + '\n'
	if SysInfo.has_intel_graphics():
		header += tr('For the best compat with your Intel hardware, you may want to use either the all open-source or Intel options.\n')
	if SysInfo.has_nvidia_graphics():
		header += tr('For the best compat with your Nvidia hardware, if recent use open-kernel, otherwise you might need to use the AUR later.\n')

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
			algo_group.set_default_by_value(ZramAlgorithm.ZSTD)
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

			return ZramConfiguration(enabled=True, algorithm=algo)
		case ResultType.Reset:
			raise ValueError('Unhandled result type')
