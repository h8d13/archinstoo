from typing import TYPE_CHECKING, Self, override

from archinstoo.default_profiles.profile import Profile, ProfileType, SelectResult
from archinstoo.lib.models.users import User
from archinstoo.lib.output import info
from archinstoo.lib.profile.profiles_handler import ProfileHandler
from archinstoo.lib.tui.curses_menu import SelectMenu
from archinstoo.lib.tui.menu_item import MenuItem, MenuItemGroup
from archinstoo.lib.tui.result import ResultType
from archinstoo.lib.tui.types import FrameProperties, PreviewStyle

if TYPE_CHECKING:
	from archinstoo.lib.installer import Installer


class ServerProfile(Profile):
	def __init__(self, current_value: list[Self] = []):
		super().__init__(
			'Server',
			ProfileType.Server,
			current_selection=current_value,
		)

	@property
	@override
	def packages(self) -> list[str]:
		return ['smartmontools']

	@override
	def do_on_select(self) -> SelectResult:
		handler = ProfileHandler()
		items = [
			MenuItem(
				p.name,
				value=p,
				preview_action=lambda x: x.value.preview_text(),
			)
			for p in handler.get_server_profiles()
		]

		group = MenuItemGroup(items, sort_items=True)
		group.set_selected_by_value(self.current_selection)

		result = SelectMenu[Self](
			group,
			allow_reset=True,
			allow_skip=True,
			preview_style=PreviewStyle.RIGHT,
			preview_size='auto',
			preview_frame=FrameProperties.max('Info'),
			multi=True,
		).run()

		match result.type_:
			case ResultType.Selection:
				selections = result.get_values()
				self.current_selection = selections
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
		for profile in self.current_selection:
			profile.provision(install_session, users)

	@override
	def install(self, install_session: Installer) -> None:
		# Install common packages for all server profiles
		install_session.add_additional_packages(self.packages)

		server_info = self.current_selection_names()
		details = ', '.join(server_info)
		info(f'Now installing the selected servers: {details}')

		for server in self.current_selection:
			info(f'Installing {server.name}...')
			install_session.add_additional_packages(server.packages)
			install_session.enable_service(server.services)
			server.install(install_session)

		info('If your selections included multiple servers with the same port, you may have to reconfigure them.')
