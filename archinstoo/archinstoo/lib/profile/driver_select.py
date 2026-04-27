from archinstoo.lib.hardware import GfxDriver, SysInfo
from archinstoo.lib.profile.base import Profile
from archinstoo.lib.translationhandler import tr
from archinstoo.lib.tui.curses_menu import SelectMenu
from archinstoo.lib.tui.menu_item import MenuItem, MenuItemGroup
from archinstoo.lib.tui.result import ResultType
from archinstoo.lib.tui.types import FrameProperties, FrameStyle, PreviewStyle


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
	items.append(MenuItem(text=tr('None'), value=None))
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
			return result.item().value
