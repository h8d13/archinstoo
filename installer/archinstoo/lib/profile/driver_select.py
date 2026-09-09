from archinstoo.lib.hardware import GFX_CUSTOM_CHOICES, GfxDriver, GfxPackage, SysInfo, detected_gfx_drivers, detected_gfx_packages
from archinstoo.lib.output import debug
from archinstoo.lib.tui.curses_menu import SelectMenu
from archinstoo.lib.tui.menu_item import MenuItem, MenuItemGroup
from archinstoo.lib.tui.result import ResultType
from archinstoo.lib.tui.types import Alignment, FrameProperties, FrameStyle, PreviewStyle


def select_gfx_packages(preset: list[GfxPackage] | None = None) -> list[GfxPackage]:
	# the custom driver: one package per line, nothing derived. A hybrid
	# laptop ticks nvidia-open next to vulkan-intel, which no preset offers
	items = [MenuItem(p.value, value=p) for p in GFX_CUSTOM_CHOICES]
	group = MenuItemGroup(items, sort_items=True)
	# first visit starts from the presets the host's GPUs map to (both halves
	# of a hybrid, plus its PRIME glue); a saved pick is left alone
	gpus = SysInfo.gpu_ids()
	group.set_selected_by_value(preset or detected_gfx_packages(gpus))

	detected = ', '.join(d.display_name() for d in detected_gfx_drivers(gpus)) or 'none'
	header = f'Detected: {detected}. Pre-ticked accordingly.\n'
	header += 'dkms and xorg packages are added from the kernel and profile picks.\n'

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
	kernels: list[str] | None = None,
) -> GfxDriver | None:
	# Somewhat convoluted function, whose job is simple.
	# Select a graphics driver from a pre-defined set of popular options.
	# This comment was stupid so I removed it. A profile should plain dictate
	# What it needs to run and be in minimal functional state.
	if not options:
		if SysInfo.arch() != 'x86_64':
			# On ARM only mesa-based drivers are available
			debug(f'arch={SysInfo.arch()}, restricting gfx driver options to mesa')
			options = [GfxDriver.MesaOpenSource]
		else:
			options = list(GfxDriver)

	def preview_driver(x: MenuItem, k: list[str] | None = kernels) -> str | None:
		if x.value is None:
			return None
		driver: GfxDriver = x.value
		return driver.packages_text(k)

	items = [MenuItem(o.display_name(), value=o, preview_action=preview_driver) for o in options]
	items.append(MenuItem(text='None', value=None))
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
		header += 'VM detected: use VM (software rendering) or VM (virtio-gpu) options.\n'
	if SysInfo.has_amd_graphics():
		header += 'AMD detected: use All open-source, AMD / ATI, or Mesa (open-source) options.\n'
	if SysInfo.has_intel_graphics():
		header += 'Intel detected: use All open-source, Intel (open-source), or Mesa (open-source) options.\n'
	if SysInfo.has_nvidia_graphics():
		header += 'Nvidia detected: Turing+ use open kernel module, older GPUs use nouveau (legacy nvidia-*xx drivers are on AUR).\n'

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
