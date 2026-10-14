import threading
from enum import Enum

from archinstoo.lib.localization.catalog import list_timezones
from archinstoo.lib.models.packages import AvailablePackage, PackageGroup
from archinstoo.lib.pm import enrich_package_info, list_available_packages, list_package_groups
from archinstoo.lib.tui.curses_menu import SelectMenu, Tui
from archinstoo.lib.tui.menu_item import MenuItem, MenuItemGroup
from archinstoo.lib.tui.prompts import prompt_choice, prompt_text, prompt_yes_no
from archinstoo.lib.tui.result import ResultType
from archinstoo.lib.tui.types import Alignment, FrameProperties, PreviewStyle


class PostInstallationAction(Enum):
	EXIT = 'exit archinstoo'
	REBOOT = 'reboot system'
	POWEROFF = 'poweroff system'
	CHROOT = 'chroot into install'


def select_ntp(preset: bool = True) -> bool:
	header = 'Would you like to use automatic time synchronization (NTP) with the default time servers?\n\n'
	header += (
		'Hardware time and other post-configuration steps might be required in order for NTP to work.\n'
		'For more information, see the systemd-timesyncd documentation\n'
	)

	choice = prompt_yes_no(header, preset)
	return preset if choice is None else choice


def select_hostname(preset: str | None = None) -> str | None:
	hostname = prompt_text('Hostname', preset=preset)
	if hostname is None:
		return preset
	return hostname or None


def select_timezone(preset: str | None = None) -> str | None:
	default = 'UTC'
	timezones = list_timezones()

	items = [MenuItem(tz, value=tz) for tz in timezones]
	return prompt_choice(items, preset, frame='Timezone', default=default, sort_items=True, allow_reset=True, reset=default)


def select_additional_packages(preset: list[str] | None = None) -> list[str]:
	if preset is None:
		preset = []

	Tui.print('Loading packages...', clear_screen=True)

	packages = list_available_packages()
	package_groups = list_package_groups()

	# repos the packages actually came from, not the ones we asked for: an
	# enabled repo whose metadata failed to load must not be advertised.
	# dict.fromkeys dedupes while holding listing order
	repos_text = ', '.join(dict.fromkeys(p.repository for p in packages.values()))

	# Additional packages (with some light weight error handling for invalid package names)
	header = f'Repositories: {repos_text}\n\n'
	header += 'Only @core, the kernel, some firmware and optional profile packages are installed.\n'
	header += 'Groups (@development-tools, ...) install with their default members.\n'
	header += 'Select any packages from the below list that should be installed additionally\n'

	# there are over 70k packages so this needs to be quick
	preset_packages: list[AvailablePackage | PackageGroup] = []
	for p in preset:
		if p in packages:
			preset_packages.append(packages[p])
		elif p in package_groups:
			preset_packages.append(package_groups[p])

	items = [
		MenuItem(
			name,
			value=pkg,
			preview_action=None,  # Will be set after menu_group is created
		)
		for name, pkg in packages.items()
	]

	items += [
		MenuItem(
			name,
			value=group,
			preview_action=lambda x: x.value.info(),
		)
		for name, group in package_groups.items()
	]

	menu_group = MenuItemGroup(items, sort_items=True)
	menu_group.set_selected_by_value(preset_packages)

	# Helper to prefetch packages in both directions in background
	def _prefetch_packages(group: MenuItemGroup, current_item: MenuItem) -> None:
		try:
			filtered_items = group.items
			current_idx = filtered_items.index(current_item)

			# Collect next 50 packages (forward)
			prefetch = []
			for i in range(current_idx + 1, min(current_idx + 51, len(filtered_items))):
				next_pkg = filtered_items[i].value
				if isinstance(next_pkg, AvailablePackage):
					prefetch.append(next_pkg)

			# Collect previous 50 packages (backward)
			for i in range(max(0, current_idx - 50), current_idx):
				prev_pkg = filtered_items[i].value
				if isinstance(prev_pkg, AvailablePackage):
					prefetch.append(prev_pkg)

			if prefetch:
				enrich_package_info(prefetch[0], prefetch=prefetch[1:])
		except ValueError, IndexError:
			pass

	# Preview function for packages - enriches current and prefetches ±50 packages
	def preview_package(item: MenuItem) -> str:
		pkg = item.value
		if isinstance(pkg, AvailablePackage):
			# Enrich current package synchronously
			enrich_package_info(pkg)
			# Prefetch next 50 in background thread
			threading.Thread(target=_prefetch_packages, args=(menu_group, item), daemon=True).start()
			return pkg.info()
		return ''

	# Set preview action for package items only
	for item in items:
		if isinstance(item.value, AvailablePackage):
			item.preview_action = preview_package

	result = SelectMenu[AvailablePackage | PackageGroup](
		menu_group,
		header=header,
		alignment=Alignment.LEFT,
		allow_reset=True,
		allow_skip=True,
		multi=True,
		preview_frame=FrameProperties.max('Package info'),
		preview_style=PreviewStyle.RIGHT,
		preview_size='auto',
	).run()

	match result.type_:
		case ResultType.Skip:
			return preset
		case ResultType.Reset:
			return []
		case ResultType.Selection:
			selected_pacakges = result.get_values()
			return [pkg.name for pkg in selected_pacakges]


def select_post_installation(elapsed_time: float | None = None) -> PostInstallationAction:
	header = 'Installation completed'
	if elapsed_time is not None:
		minutes = int(elapsed_time // 60)
		seconds = int(elapsed_time % 60)
		header += f' in {minutes}m{seconds}s\n'
	header += 'What would you like to do next?\n'
	header += '\nAfter reboot, remove the installation medium\n'

	items = [MenuItem(action.value, value=action) for action in PostInstallationAction]
	return prompt_choice(items, header=header, allow_skip=False)
