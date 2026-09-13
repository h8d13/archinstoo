from typing import TYPE_CHECKING, Self, override

from archinstoo.lib.exceptions import SysCallError
from archinstoo.lib.output import debug, info, warn
from archinstoo.lib.profile.base import GreeterType, Profile, ProfileType, SelectResult
from archinstoo.lib.profile.profiles_handler import ProfileHandler
from archinstoo.lib.tui.curses_menu import SelectMenu
from archinstoo.lib.tui.menu_item import MenuItem, MenuItemGroup
from archinstoo.lib.tui.result import ResultType
from archinstoo.lib.tui.types import FrameProperties, PreviewStyle

if TYPE_CHECKING:
	from archinstoo.lib.installer import Installer
	from archinstoo.lib.models.users import User


class DesktopProfile(Profile):
	def __init__(self, current_selection: list[Self] | None = None) -> None:
		super().__init__(
			'desktop',
			ProfileType.Desktop,
			current_selection=current_selection,
		)

	@property
	@override
	def packages(self) -> list[str]:
		return [
			'smartmontools',
			'xdg-utils',
			'xdg-user-dirs',
		]

	@property
	@override
	def default_greeter_type(self) -> GreeterType | None:
		combined_greeters: dict[GreeterType, int] = {}
		for profile in sorted(self.current_selection, key=lambda p: p.custom_settings.get('seat_access') != 'seatd'):
			if profile.default_greeter_type:
				combined_greeters.setdefault(profile.default_greeter_type, 0)
				combined_greeters[profile.default_greeter_type] += 1

		if len(combined_greeters) >= 1:
			chosen = next(iter(combined_greeters))
			if len(combined_greeters) > 1:
				debug(f'Multiple default greeters {[g.value for g in combined_greeters]}, using {chosen.value}')
			return chosen

		return None

	def _do_on_select_profiles(self) -> None:
		for profile in self.current_selection:
			profile.do_on_select()

	@override
	def do_on_select(self) -> SelectResult:
		handler = ProfileHandler()
		items = [
			MenuItem(
				p.name,
				value=p,
				preview_action=lambda x: x.value.preview_text(),
			)
			for p in handler.get_desktop_profiles()
		]

		group = MenuItemGroup(items, sort_items=True, sort_case_sensitive=False)
		group.set_selected_by_value(self.current_selection)

		result = SelectMenu[Self](
			group,
			multi=True,
			allow_reset=True,
			allow_skip=True,
			preview_style=PreviewStyle.RIGHT,
			preview_size='auto',
			preview_frame=FrameProperties.max('Info'),
		).run()

		match result.type_:
			case ResultType.Selection:
				self.current_selection = result.get_values()
				self._do_on_select_profiles()
				return SelectResult.NewSelection
			case ResultType.Skip:
				return SelectResult.SameSelection
			case ResultType.Reset:
				return SelectResult.ResetCurrent

	@override
	def post_install(self, install_session: Installer) -> None:
		for profile in self.current_selection:
			profile.post_install(install_session)

	@override
	def provision(self, install_session: Installer, users: list[User]) -> None:
		# xdg-user-dirs only runs itself from /etc/xdg/autostart or
		# graphical-session-pre.target, and bare WMs (labwc, sway, i3...) reach
		# neither. Create ~/Documents & co here instead; run_as goes through a
		# login shell, so profile.d/locale.sh hands it the target LANG and the
		# names come out localized
		for user in users:
			try:
				install_session.arch_chroot(['xdg-user-dirs-update'], run_as=user.username)
			except SysCallError as err:
				warn(f'xdg-user-dirs-update failed for {user.username}: {err}')

		for profile in self.current_selection:
			profile.provision(install_session, users)

	@override
	def install(self, install_session: Installer) -> None:
		# Install common packages for all desktop environments
		install_session.add_additional_packages(self.effective_packages())

		for profile in self.current_selection:
			info(f'Installing profile {profile.name}...')

			install_session.add_additional_packages(profile.effective_packages())
			install_session.enable_service(profile.services)

			profile.install(install_session)
