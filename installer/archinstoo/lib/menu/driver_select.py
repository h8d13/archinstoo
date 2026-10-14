from archinstoo.lib.hardware import SysInfo
from archinstoo.lib.models.graphics import GfxDriver, GfxPackage, gfx_custom_choices, gfx_drivers
from archinstoo.lib.output import debug
from archinstoo.lib.tui.curses_menu import SelectMenu
from archinstoo.lib.tui.menu_item import MenuItem, MenuItemGroup
from archinstoo.lib.tui.result import ResultType
from archinstoo.lib.tui.types import Alignment, FrameProperties, FrameStyle, PreviewStyle


def select_gfx_packages(preset: list[GfxPackage] | None = None) -> list[GfxPackage]:
	# the custom driver: one package per line, nothing derived. A hybrid
	# laptop ticks both vendors' extras, which no preset offers
	choices = gfx_custom_choices(SysInfo.arch())
	items = [MenuItem(p.value, value=p) for p in choices]
	group = MenuItemGroup(items, sort_items=True)
	# a pick saved on the other arch may hold names this list lacks
	group.set_selected_by_value([p for p in preset or [] if p in choices])

	header = 'mesa-vulkan-drivers carries every vulkan driver (radv, anv, nvk, panfrost, ...).\n'

	result = SelectMenu[GfxPackage](
		group,
		header=header,
		allow_skip=True,
		allow_reset=True,
		alignment=Alignment.CENTER,
		frame=FrameProperties.min('Graphics packages'),
		multi=True,
	).run()

	match result.type_:
		case ResultType.Skip:
			return list(preset or [])
		case ResultType.Reset:
			return []
		case ResultType.Selection:
			return result.get_values()


def select_driver(
	options: list[GfxDriver] | None = None,
	preset: GfxDriver | None = None,
) -> GfxDriver | None:
	# Somewhat convoluted function, whose job is simple.
	# Select a graphics driver from a pre-defined set of popular options.
	# This comment was stupid so I removed it. A profile should plain dictate
	# What it needs to run and be in minimal functional state.
	if not options:
		options = gfx_drivers(SysInfo.arch())
		debug(f'arch={SysInfo.arch()}, gfx driver options: {[o.value for o in options]}')

	def preview_driver(x: MenuItem) -> str | None:
		if x.value is None:
			return None
		driver: GfxDriver = x.value
		return driver.packages_text()

	items = [MenuItem(o.display_name(), value=o, preview_action=preview_driver) for o in options]
	items.append(MenuItem(text='None', value=None))
	group = MenuItemGroup(items, sort_items=True)
	defaults = [o for o in (GfxDriver.AllOpenSource, GfxDriver.MesaOpenSource) if o in options]
	group.set_default_by_value(defaults[0] if defaults else options[0])

	if preset is not None:
		group.set_focus_by_value(preset)

	header = "Nvidia: nouveau/nvk here; the proprietary module is RPM Fusion's akmod-nvidia.\n"
	header += 'Hybrid laptops: use Custom to pick packages for both GPUs.\n'

	result = SelectMenu[GfxDriver](
		group,
		header=header,
		allow_skip=True,
		allow_reset=True,
		preview_size='auto',
		preview_style=PreviewStyle.BOTTOM,
		preview_frame=FrameProperties('Info', h_frame_style=FrameStyle.MIN),
	).run()

	match result.type_:
		case ResultType.Skip:
			return preset
		case ResultType.Reset:
			return None
		case ResultType.Selection:
			return result.item().value
