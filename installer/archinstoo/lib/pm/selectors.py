import threading

from archinstoo.lib.models.packages import AvailablePackage, PackageGroup
from archinstoo.lib.pm.packages import enrich_package_info, list_available_packages
from archinstoo.lib.tui.curses_menu import EditMenu, SelectMenu, Tui
from archinstoo.lib.tui.menu_item import MenuItem, MenuItemGroup
from archinstoo.lib.tui.result import ResultType
from archinstoo.lib.tui.types import Alignment, FrameProperties, PreviewStyle


def select_additional_packages(preset: list[str] | None = None) -> list[str]:
	if preset is None:
		preset = []

	Tui.print('Loading packages...', clear_screen=True)

	packages = list_available_packages()
	package_groups = PackageGroup.from_available_packages(packages)

	# repos the packages actually came from, not the ones we asked for: a repo
	# enabled in pacman.conf whose db failed to sync must not be advertised.
	# dict.fromkeys dedupes while holding conf order
	repos_text = ', '.join(dict.fromkeys(p.repository for p in packages.values()))

	# Additional packages (with some light weight error handling for
	# invalid package names)
	header = f'Repositories: {repos_text}\n\n'
	header += (
		'Only packages such as base, linux, some firmware, efibootmgr and '
		'optional profile packages are installed.\n'
	)
	header += (
		'Note: base-devel is no longer installed by default. Add it here if '
		'you need build tools + devtools for tooling..\n'
	)
	header += (
		'Select any packages from the below list that should be installed '
		'additionally\n'
	)

	# there are over 15k packages so this needs to be quick
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
			for i in range(
				current_idx + 1,
				min(current_idx + 51, len(filtered_items)),
			):
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
			threading.Thread(
				target=_prefetch_packages,
				args=(menu_group, item),
				daemon=True,
			).start()
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


def select_aur_packages(preset: list[str] | None = None) -> list[str]:
	from archinstoo.lib.grimoire import exists_in_aur_mirror

	if preset is None:
		preset = []

	base_header = 'Enter AUR package names separated by commas\n'
	base_header += (
		'git and the makepkg toolchain (base-devel minus sudo) will be '
		'installed automatically\n'
	)

	error_msg = ''
	current_text = ', '.join(preset) if preset else ''

	while True:
		header = base_header
		if error_msg:
			header += '\n' + error_msg

		result = EditMenu(
			'AUR packages',
			header=header,
			alignment=Alignment.CENTER,
			allow_skip=True,
			allow_reset=True,
			default_text=current_text,
		).input()

		match result.type_:
			case ResultType.Skip:
				return preset
			case ResultType.Reset:
				return []
			case ResultType.Selection:
				raw = result.text().strip()
				if not raw:
					return []

				names = [
					name.strip()
					for name in raw.split(',')
					if name.strip()
				]
				if not names:
					return []

				Tui.print(
					'Validating AUR packages...', clear_screen=True
				)
				invalid = [
					n for n in names if not exists_in_aur_mirror(n)
				]

				if not invalid:
					return names

				current_text = ', '.join(
					n for n in names if n not in invalid
				)
				error_msg = (
					'Not found in AUR: ' + ', '.join(invalid) + '\n'
				)
