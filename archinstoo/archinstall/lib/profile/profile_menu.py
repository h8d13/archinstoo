from typing import TYPE_CHECKING, override

if TYPE_CHECKING:
	from archinstall.lib.profile.profiles_handler import ProfileHandler

from archinstall.default_profiles.profile import DisplayServer, GreeterType, Profile
from archinstall.lib.hardware import GfxDriver
from archinstall.lib.interactions.system_conf import select_driver
from archinstall.lib.menu.abstract_menu import AbstractSubMenu
from archinstall.lib.models.profile import ProfileConfiguration
from archinstall.lib.translationhandler import tr
from archinstall.lib.tui.curses_menu import SelectMenu
from archinstall.lib.tui.menu_item import MenuItem, MenuItemGroup
from archinstall.lib.tui.result import ResultType
from archinstall.lib.tui.types import Alignment, FrameProperties


class ProfileMenu(AbstractSubMenu[ProfileConfiguration]):
	def __init__(
		self,
		preset: ProfileConfiguration | None = None,
		kernels: list[str] | None = None,
	):
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
				text=tr('Type'),
				action=self._select_profiles,
				value=self._profile_config.profiles,
				preview_action=self._preview_profiles,
				key='profiles',
			),
			MenuItem(
				text=tr('Graphics driver'),
				action=self.select_gfx_driver,
				value=self._profile_config.gfx_driver if self._profile_config.profiles else None,
				preview_action=self._prev_gfx,
				enabled=bool(self._profile_config.profiles and self._profile_config.display_servers()),
				dependencies=['profiles'],
				key='gfx_driver',
			),
			MenuItem(
				text=tr('Greeter'),
				action=lambda x: select_greeter(preset=x),
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

		if profiles:
			# Check if any profile needs display servers
			has_display_servers = any(p.display_servers() for p in profiles)
			if has_display_servers:
				self._item_group.find_by_key('gfx_driver').enabled = True
			else:
				self._item_group.find_by_key('gfx_driver').enabled = False
				self._item_group.find_by_key('gfx_driver').value = None

			# Check if any profile supports greeter
			supports_greeter = any(p.is_greeter_supported() for p in profiles)
			if not supports_greeter:
				self._item_group.find_by_key('greeter').enabled = False
				self._item_group.find_by_key('greeter').value = None
			else:
				self._item_group.find_by_key('greeter').enabled = True
				# Get default greeter from first desktop profile
				for p in profiles:
					if p.default_greeter_type:
						self._item_group.find_by_key('greeter').value = p.default_greeter_type
						break
		else:
			self._item_group.find_by_key('gfx_driver').value = None
			self._item_group.find_by_key('greeter').value = None

		return profiles

	def select_gfx_driver(self, preset: GfxDriver | None = None) -> GfxDriver | None:
		driver = preset
		profiles: list[Profile] = self._item_group.find_by_key('profiles').value or []

		if profiles:
			# Use first profile with display servers for driver selection
			for profile in profiles:
				if profile.display_servers():
					driver = select_driver(preset=preset, profile=profile, kernels=self._kernels)
					break

		return driver

	def _prev_gfx(self, item: MenuItem) -> str | None:
		if item.value:
			driver = item.get_value().value
			profiles: list[Profile] = self._item_group.find_by_key('profiles').value or []
			servers: set[DisplayServer] = set()
			for profile in profiles:
				servers.update(profile.display_servers())
			packages = item.get_value().packages_text(servers or None, self._kernels)
			return f'Driver: {driver}\n{packages}'
		return None

	def _prev_greeter(self, item: MenuItem) -> str | None:
		if item.value:
			return f'{tr("Greeter")}: {item.value.value}'
		return None

	def _preview_profiles(self, item: MenuItem) -> str | None:
		profiles: list[Profile] = item.value or []
		text = ''

		if profiles:
			text += tr('Selected profiles: ')
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
				text += tr('Installed packages') + ':\n'
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
		items = [MenuItem(greeter.name if greeter == GreeterType.Nogreeter else greeter.value, value=greeter) for greeter in GreeterType]
		group = MenuItemGroup(items, sort_items=True)

		default: GreeterType | None = None
		if preset is not None:
			default = preset
		elif profile is not None:
			default_greeter = profile.default_greeter_type
			default = default_greeter if default_greeter else None

		group.set_default_by_value(default)

		result = SelectMenu[GreeterType](
			group,
			allow_skip=True,
			frame=FrameProperties.min(tr('Greeter')),
			alignment=Alignment.CENTER,
		).run()

		match result.type_:
			case ResultType.Skip:
				return preset
			case ResultType.Selection:
				return result.get_value()
			case ResultType.Reset:
				raise ValueError('Unhandled result type')

	return None


def select_profiles(
	current_profiles: list[Profile] | None = None,
	header: str | None = None,
	allow_reset: bool = True,
	profile_handler: ProfileHandler | None = None,
) -> list[Profile]:
	from archinstall.lib.profile.profiles_handler import ProfileHandler

	handler = profile_handler or ProfileHandler()
	top_level_profiles = handler.get_top_level_profiles()

	if header is None:
		header = tr('Select one or more profiles (Desktop + Server supported)') + '\n'

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
		frame=FrameProperties.min(tr('Profiles')),
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
