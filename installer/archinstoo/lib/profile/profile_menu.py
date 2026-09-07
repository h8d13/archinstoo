from typing import TYPE_CHECKING, override

if TYPE_CHECKING:
	from archinstoo.lib.profile.profiles_handler import ProfileHandler

from archinstoo.lib.hardware import GfxDriver, GfxPackage
from archinstoo.lib.menu.abstract_menu import CONFIG_KEY, AbstractSubMenu
from archinstoo.lib.models.profile import ProfileConfiguration
from archinstoo.lib.profile.base import GreeterType, Profile, ProfileType
from archinstoo.lib.profile.driver_select import select_driver, select_gfx_packages
from archinstoo.lib.tui.curses_menu import SelectMenu
from archinstoo.lib.tui.menu_item import MenuItem, MenuItemGroup
from archinstoo.lib.tui.prompts import prompt_choice
from archinstoo.lib.tui.result import ResultType
from archinstoo.lib.tui.types import Alignment, FrameProperties


class ProfileMenu(AbstractSubMenu[ProfileConfiguration]):
	def __init__(
		self,
		preset: ProfileConfiguration | None = None,
		kernels: list[str] | None = None,
	) -> None:
		if preset:
			self._profile_config = preset
		else:
			self._profile_config = ProfileConfiguration()

		self._kernels = kernels

		menu_options = self._define_menu_options()
		self._item_group = MenuItemGroup(menu_options, checkmarks=True)

		super().__init__(
			self._item_group,
			self._profile_config,
			allow_reset=True,
		)

	def _define_menu_options(self) -> list[MenuItem]:
		return [
			MenuItem(
				text='Type',
				action=self._select_profiles,
				value=self._profile_config.profiles,
				preview_action=self._preview_profiles,
				key='profiles',
			),
			MenuItem(
				text='Customize packages',
				action=self._customize_packages,
				value=None,
				preview_action=self._prev_customize_packages,
				enabled=any(p.profile_type != ProfileType.Minimal for p in self._profile_config.profiles),
				dependencies=['profiles'],
				key=f'{CONFIG_KEY}_customize_packages',
			),
			MenuItem(
				text='Graphics driver',
				action=self.select_gfx_driver,
				value=self._profile_config.gfx_driver if self._profile_config.profiles else None,
				preview_action=self._prev_gfx,
				enabled=bool(self._profile_config.profiles and self._profile_config.display_servers()),
				dependencies=['profiles'],
				key='gfx_driver',
			),
			MenuItem(
				text='Graphics packages',
				action=select_gfx_packages,
				value=self._profile_config.gfx_packages,
				preview_action=self._prev_gfx_packages,
				enabled=self._profile_config.gfx_driver is GfxDriver.Custom,
				dependencies=['gfx_driver'],
				key='gfx_packages',
			),
			MenuItem(
				text='Greeter',
				action=self.select_greeter,
				value=self._profile_config.greeter if self._profile_config.profiles and self._profile_config.is_greeter_supported() else None,
				enabled=bool(self._profile_config.profiles and self._profile_config.is_greeter_supported()),
				preview_action=self._prev_greeter,
				dependencies=['profiles'],
				key='greeter',
			),
		]

	@override
	def run(self, additional_title: str | None = None) -> ProfileConfiguration | None:
		super().run(additional_title=additional_title)
		return self._profile_config

	def _select_profiles(self, preset: list[Profile]) -> list[Profile]:
		profiles = select_profiles(preset)
		# skipping the list hands back the preset: re-seeding the greeter then
		# would drop a deliberate pick for the profile default, and just
		# entering the menu is enough to trigger it
		changed = profiles != preset

		if profiles:
			# Check if any profile needs display servers
			has_display_servers = any(p.display_servers() for p in profiles)
			if has_display_servers:
				self._item_group.find_by_key('gfx_driver').enabled = True
			else:
				self._item_group.find_by_key('gfx_driver').enabled = False
				self._item_group.find_by_key('gfx_driver').value = None
				self._set_gfx_packages(None)

			# Check if any profile supports greeter
			supports_greeter = any(p.is_greeter_supported() for p in profiles)
			if not supports_greeter:
				self._item_group.find_by_key('greeter').enabled = False
				self._item_group.find_by_key('greeter').value = None
			else:
				greeter_item = self._item_group.find_by_key('greeter')
				greeter_item.enabled = True
				# Get default greeter from first desktop profile
				if changed or greeter_item.value is None:
					for p in profiles:
						if p.default_greeter_type:
							greeter_item.value = p.default_greeter_type
							break
		else:
			self._item_group.find_by_key('gfx_driver').value = None
			self._set_gfx_packages(None)
			self._item_group.find_by_key('greeter').value = None

		customize_item = self._item_group.find_by_key(f'{CONFIG_KEY}_customize_packages')
		if customize_item is not None:
			customize_item.enabled = any(p.profile_type != ProfileType.Minimal for p in profiles)

		return profiles

	def select_greeter(self, preset: GreeterType | None = None) -> GreeterType | None:
		profiles: list[Profile] = self._item_group.find_by_key('profiles').value or []
		profile = next((p for p in profiles if p.is_greeter_supported()), None)
		return select_greeter(profile=profile, preset=preset)

	def _customize_packages(self, _preset: None = None) -> None:
		profiles: list[Profile] = self._item_group.find_by_key('profiles').value or []
		targets = [p for pr in profiles for p in [pr, *(pr.current_selection or [])]]

		for profile in targets:
			pkgs = profile.packages
			if not pkgs:
				continue

			excluded = set(profile.custom_settings.get('excluded_packages') or [])
			group = MenuItemGroup([MenuItem(p, value=p) for p in sorted(pkgs)])
			group.set_selected_by_value([p for p in pkgs if p not in excluded])

			result = SelectMenu[str](
				group,
				header='Toggle packages to install' + '\n',
				allow_skip=True,
				alignment=Alignment.CENTER,
				frame=FrameProperties.min(profile.name),
				multi=True,
			).run()

			if result.type_ != ResultType.Selection:
				continue

			new_excluded = [p for p in pkgs if p not in set(result.get_values() or [])]
			profile.custom_settings['excluded_packages'] = new_excluded or None

	def select_gfx_driver(self, preset: GfxDriver | None = None) -> GfxDriver | None:
		driver = preset
		profiles: list[Profile] = self._item_group.find_by_key('profiles').value or []

		if profiles:
			# Use first profile with display servers for driver selection
			for profile in profiles:
				if profile.display_servers():
					driver = select_driver(preset=preset, kernels=self._kernels)
					break

		# custom chains straight into the package list; any other driver
		# owns its packages and the list item goes dark
		self._set_gfx_packages(driver)
		return driver

	def _set_gfx_packages(self, driver: GfxDriver | None) -> None:
		item = self._item_group.find_by_key('gfx_packages')
		item.enabled = driver is GfxDriver.Custom
		if driver is GfxDriver.Custom:
			item.value = select_gfx_packages(item.value)
		else:
			item.value = []

	def _prev_gfx_packages(self, item: MenuItem) -> str | None:
		packages: list[GfxPackage] = item.value or []
		if not packages:
			return 'No packages picked'
		return 'Graphics packages' + ':\n' + ''.join(f'\t- {name}\n' for name in sorted(p.value for p in packages))

	def _prev_customize_packages(self, _item: MenuItem) -> str | None:
		profiles: list[Profile] = self._item_group.find_by_key('profiles').value or []
		excluded = sorted(
			{pkg for pr in profiles for p in [pr, *(pr.current_selection or [])] for pkg in (p.custom_settings.get('excluded_packages') or [])}
		)
		if not excluded:
			return 'No packages excluded'
		return 'Excluded packages' + ':\n' + '\n'.join(f'\t- {pkg}' for pkg in excluded)

	def _prev_gfx(self, item: MenuItem) -> str | None:
		if item.value:
			driver = item.get_value().value
			packages = item.get_value().packages_text(self._kernels)
			return f'{"Graphics driver"}: {driver}\n{packages}'
		return None

	def _prev_greeter(self, item: MenuItem) -> str | None:
		if item.value:
			return f'{"Greeter"}: {item.value.value}'
		return None

	def _preview_profiles(self, item: MenuItem) -> str | None:
		profiles: list[Profile] = item.value or []
		text = ''

		if profiles:
			text += 'Selected profiles: '
			text += ', '.join([p.name for p in profiles]) + '\n'

			for profile in profiles:
				if sub_profiles := profile.current_selection:
					text += f'  {profile.name}: '
					text += ', '.join([p.name for p in sub_profiles]) + '\n'

			# Collect all packages
			all_packages: set[str] = set()
			for profile in profiles:
				if profile.packages:
					all_packages.update(profile.packages)
				for sub in profile.current_selection:
					if sub.packages:
						all_packages.update(sub.packages)

			if all_packages:
				text += 'Installed packages' + ':\n'
				for pkg in sorted(all_packages):
					text += f'\t- {pkg}\n'

			if text:
				return text

		return None


def select_greeter(
	profile: Profile | None = None,
	preset: GreeterType | None = None,
) -> GreeterType | None:
	if not profile or profile.is_greeter_supported():
		items = [MenuItem(g.value, value=g) for g in GreeterType]
		items.append(MenuItem(text='None', value=None))

		default: GreeterType | None = None
		if preset is not None:
			default = preset
		elif profile is not None:
			default_greeter = profile.default_greeter_type
			default = default_greeter or None

		return prompt_choice(items, preset, frame='Greeter', default=default, sort_items=True)

	return None


def select_profiles(
	current_profiles: list[Profile] | None = None,
	header: str | None = None,
	allow_reset: bool = True,
	profile_handler: ProfileHandler | None = None,
) -> list[Profile]:
	from archinstoo.lib.profile.profiles_handler import ProfileHandler

	handler = profile_handler or ProfileHandler()
	top_level_profiles = handler.get_top_level_profiles()

	if header is None:
		header = 'Select one or more profiles (Desktop + Server supported)' + '\n'

	items = [MenuItem(p.name, value=p) for p in top_level_profiles]
	group = MenuItemGroup(items, sort_items=True)

	if current_profiles:
		for profile in current_profiles:
			group.set_selected_by_value(profile)

	result = SelectMenu[Profile](
		group,
		header=header,
		allow_reset=allow_reset,
		allow_skip=True,
		multi=True,
		alignment=Alignment.CENTER,
		frame=FrameProperties.min('Profiles'),
	).run()

	match result.type_:
		case ResultType.Reset:
			handler.reset_top_level_profiles()
			return []
		case ResultType.Skip:
			return current_profiles or []
		case ResultType.Selection:
			selected_profiles: list[Profile] = result.get_values()

			# Call do_on_select for each profile and filter out failed ones
			valid_profiles: list[Profile] = []
			for profile in selected_profiles:
				select_result = profile.do_on_select()

				if not select_result:
					continue

				match select_result:
					case select_result.NewSelection:
						valid_profiles.append(profile)
					case select_result.ResetCurrent:
						profile.reset()
					case select_result.SameSelection:
						valid_profiles.append(profile)

			# Reset profiles that were not selected
			handler.reset_top_level_profiles(exclude=valid_profiles)

			return valid_profiles
