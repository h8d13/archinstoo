from typing import assert_never, cast, override

from archinstoo.default_profiles.profile import Profile
from archinstoo.lib.hardware import GfxDriver, SysInfo
from archinstoo.lib.menu.abstract_menu import AbstractSubMenu
from archinstoo.lib.models.application import ZramAlgorithm, ZramConfiguration
from archinstoo.lib.models.kernel import KernelConfiguration
from archinstoo.lib.translationhandler import tr
from archinstoo.lib.tui.curses_menu import SelectMenu
from archinstoo.lib.tui.menu_item import MenuItem, MenuItemGroup
from archinstoo.lib.tui.result import ResultType
from archinstoo.lib.tui.types import Alignment, FrameProperties, FrameStyle, Orientation, PreviewStyle


def _select_kernels(preset: list[str]) -> list[str]:
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


def _yes_no(preset: bool, header: str) -> bool:
	group = MenuItemGroup.yes_no()
	group.set_focus_by_value(preset)

	result = SelectMenu[bool](
		group,
		header=header,
		columns=2,
		orientation=Orientation.HORIZONTAL,
		alignment=Alignment.CENTER,
		allow_skip=True,
	).run()

	match result.type_:
		case ResultType.Skip:
			return preset
		case ResultType.Selection:
			return result.item() == MenuItem.yes()
		case ResultType.Reset:
			raise ValueError('Unhandled result type')


def _select_headers(preset: bool) -> bool:
	header = tr('Install kernel headers?') + '\n\n'
	header += tr('Useful for building out-of-tree drivers or DKMS modules,') + '\n'
	header += tr('especially for non-standard kernel variants.') + '\n'
	return _yes_no(preset, header)


class KernelMenu(AbstractSubMenu[KernelConfiguration]):
	def __init__(self, config: KernelConfiguration):
		self._kernel_conf = config
		menu_options = self._define_menu_options()

		self._item_group = MenuItemGroup(menu_options, sort_items=False, checkmarks=True)
		super().__init__(
			self._item_group,
			config=self._kernel_conf,
		)

	def _define_menu_options(self) -> list[MenuItem]:
		return [
			MenuItem(
				text=tr('Kernels'),
				action=_select_kernels,
				value=self._kernel_conf.kernels,
				preview_action=self._prev_kernel,
				key='kernels',
			),
			MenuItem(
				text=tr('Headers'),
				action=_select_headers,
				value=self._kernel_conf.headers,
				preview_action=self._prev_kernel,
				key='headers',
			),
		]

	def _prev_kernel(self, item: MenuItem) -> str:
		kernels: list[str] = self._item_group.find_by_key('kernels').value or []
		headers = cast(bool, self._item_group.find_by_key('headers').value)
		kernel_str = ', '.join(kernels) if kernels else tr('None')
		output = f'{tr("Kernels")}: {kernel_str}\n'
		status = tr('Enabled') if headers else tr('Disabled')
		output += f'{tr("Headers")}: {status}'
		return output

	@override
	def run(self, additional_title: str | None = None) -> KernelConfiguration:
		super().run(additional_title=additional_title)
		return self._kernel_conf


def _select_swap_enabled(preset: bool) -> bool:
	return _yes_no(preset, tr('Would you like to use swap on zram?') + '\n')


def _select_zram_algo(preset: ZramAlgorithm, header: str, default: ZramAlgorithm) -> ZramAlgorithm:
	algo_group = MenuItemGroup.from_enum(ZramAlgorithm, sort_items=False)
	algo_group.set_default_by_value(default)
	algo_group.set_focus_by_value(preset)

	result = SelectMenu[ZramAlgorithm](
		algo_group,
		header=header,
		alignment=Alignment.CENTER,
		allow_skip=True,
	).run()

	match result.type_:
		case ResultType.Skip:
			return preset
		case ResultType.Selection:
			return result.get_value()
		case ResultType.Reset:
			raise ValueError('Unhandled result type')
		case _:
			assert_never(result.type_)


class SwapMenu(AbstractSubMenu[ZramConfiguration]):
	def __init__(self, config: ZramConfiguration):
		self._swap_conf = config
		menu_options = self._define_menu_options()

		self._item_group = MenuItemGroup(menu_options, sort_items=False, checkmarks=True)
		super().__init__(
			self._item_group,
			config=self._swap_conf,
		)

	def _define_menu_options(self) -> list[MenuItem]:
		return [
			MenuItem(
				text=tr('Enable zram'),
				action=_select_swap_enabled,
				value=self._swap_conf.enabled,
				preview_action=self._prev_swap,
				key='enabled',
			),
			MenuItem(
				text=tr('Compression algorithm'),
				action=lambda p: _select_zram_algo(p, tr('Select zram compression algorithm:') + '\n', ZramAlgorithm.ZSTD),
				value=self._swap_conf.algorithm,
				preview_action=self._prev_swap,
				key='algorithm',
			),
			MenuItem(
				text=tr('Decompression algorithm'),
				action=lambda p: _select_zram_algo(p, tr('Select zram decompression algorithm:') + '\n', ZramAlgorithm.LZ4),
				value=self._swap_conf.decompression_algorithm,
				preview_action=self._prev_swap,
				key='decompression_algorithm',
			),
		]

	def _prev_swap(self, item: MenuItem) -> str:
		enabled = cast(bool, self._item_group.find_by_key('enabled').value)
		output = f'{tr("Swap on zram")}: '
		output += tr('Enabled') if enabled else tr('Disabled')
		if enabled:
			algo = cast(ZramAlgorithm, self._item_group.find_by_key('algorithm').value)
			decomp = cast(ZramAlgorithm, self._item_group.find_by_key('decompression_algorithm').value)
			output += f'\n{tr("Compression algorithm")}: {algo.value}'
			output += f'\n{tr("Decompression algorithm")}: {decomp.value}'
		return output

	@override
	def sync_all_to_config(self) -> None:
		# ZramConfiguration is frozen, so rebuild instead of setattr
		enabled = cast(bool, self._item_group.find_by_key('enabled').value)
		algo = cast(ZramAlgorithm, self._item_group.find_by_key('algorithm').value)
		decomp = cast(ZramAlgorithm, self._item_group.find_by_key('decompression_algorithm').value)
		self._swap_conf = ZramConfiguration(enabled=enabled, algorithm=algo, decompression_algorithm=decomp)
		self._config = self._swap_conf

	@override
	def run(self, additional_title: str | None = None) -> ZramConfiguration:
		super().run(additional_title=additional_title)
		return self._swap_conf


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
	_sysinfo = SysInfo()

	if not options:
		if _sysinfo.arch() != 'x86_64':
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
	if GfxDriver.MesaOpenSource in options and (_sysinfo.is_vm() or _sysinfo.arch() != 'x86_64'):
		default_driver = GfxDriver.MesaOpenSource
	elif GfxDriver.AllOpenSource in options:
		default_driver = GfxDriver.AllOpenSource
	else:
		default_driver = options[0]
	group.set_default_by_value(default_driver)

	if preset is not None:
		group.set_focus_by_value(preset)

	header = ''
	if _sysinfo.is_vm():
		header += tr('VM detected: use VM (software rendering) or VM (virtio-gpu) options.\n')
	if _sysinfo.has_amd_graphics():
		header += tr('AMD detected: use All open-source, AMD / ATI, or Mesa (open-source) options.\n')
	if _sysinfo.has_intel_graphics():
		header += tr('Intel detected: use All open-source, Intel (open-source), or Mesa (open-source) options.\n')
	if _sysinfo.has_nvidia_graphics():
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
