import re
from typing import override

from archinstall.lib.translationhandler import tr
from archinstall.lib.tui.curses_menu import EditMenu, SelectMenu
from archinstall.lib.tui.menu_item import MenuItem, MenuItemGroup
from archinstall.lib.tui.prompts import get_password
from archinstall.lib.tui.result import ResultType
from archinstall.lib.tui.types import Alignment, Orientation

from ..menu.list_manager import ListManager
from ..models.users import User


class UserList(ListManager[User]):
	def __init__(self, prompt: str, lusers: list[User]):
		self._actions = [
			tr('Add a user'),
			tr('Manage stash URLs'),
			tr('Change password'),
			tr('Promote/Demote user'),
			tr('Delete User'),
		]

		super().__init__(
			lusers,
			[self._actions[0]],
			self._actions[1:],
			prompt,
		)

	@override
	def selected_action_display(self, selection: User) -> str:
		return selection.username

	@override
	def handle_action(self, action: str, entry: User | None, data: list[User]) -> list[User]:
		if action == self._actions[0]:  # add
			if (new_user := self._add_user()) is not None:
				# in case a user with the same username as an existing user
				# was created we'll replace the existing one
				data = [d for d in data if d.username != new_user.username]
				data += [new_user]
				self._data = data  # update before showing sub-menu
				self._run_actions_on_entry(new_user)
		elif action == self._actions[1] and entry:  # manage stash urls
			user = next(filter(lambda x: x == entry, data))
			user.stash_urls = self._manage_stash_urls(user)
		elif action == self._actions[2] and entry:  # change password
			header = f'{tr("User")}: {entry.username}\n'
			new_password = get_password(tr('Password'), header=header)

			if new_password:
				user = next(filter(lambda x: x == entry, data))
				user.password = new_password
		elif action == self._actions[3] and entry:  # promote/demote
			user = next(filter(lambda x: x == entry, data))
			user.elev = not user.elev
		elif action == self._actions[4] and entry:  # delete
			data = [d for d in data if d != entry]

		return data

	def _check_for_correct_username(self, username: str | None) -> str | None:
		if username is not None:
			if re.match(r'^[a-z_][a-z0-9_-]*\$?$', username) and len(username) <= 32:
				return None
		return tr('The username you entered is invalid')

	def _validate_stash_url(self, url: str | None) -> str | None:
		if not url:
			return None
		# Strip optional #branch suffix, validate git URL
		if re.match(r'^(https?://|git@|git://)', url.partition('#')[0]):
			return None
		return tr('Invalid git URL')

	def _manage_stash_urls(self, user: User) -> list[str]:
		urls = list(user.stash_urls)

		items = [MenuItem(url, url) for url in urls]
		items.append(MenuItem(tr('Add new stash URL'), '__add__'))

		if urls:
			header = f'{tr("User")}: {user.username}\n{tr("Select URL to remove, or add new")}\n'
		else:
			header = f'{tr("User")}: {user.username}\n{tr("No stash URLs configured")}\n'

		group = MenuItemGroup(items)
		result = SelectMenu[str](group, header=header, allow_skip=True, alignment=Alignment.CENTER).run()

		match result.type_:
			case ResultType.Skip:
				return urls
			case ResultType.Selection:
				selected = str(result.item().value)
				if selected == '__add__':
					if new_url := self._get_stash_url():
						urls.append(new_url)
				else:
					urls.remove(selected)

		return urls

	def _get_stash_url(self) -> str | None:
		header = f'{tr("Format")}: https://provider.com/user/repo#branch\n{tr("Branch is optional")}\n'
		result = EditMenu(
			tr('Stash URL'),
			header=header,
			allow_skip=True,
			validator=self._validate_stash_url,
		).input()

		match result.type_:
			case ResultType.Skip:
				return None
			case ResultType.Selection:
				return result.text() or None
			case _:
				return None

	def _add_user(self) -> User | None:
		editResult = EditMenu(
			tr('Username'),
			allow_skip=True,
			validator=self._check_for_correct_username,
		).input()

		match editResult.type_:
			case ResultType.Skip:
				return None
			case ResultType.Selection:
				username = editResult.text()
			case _:
				raise ValueError('Unhandled result type')

		if not username:
			return None

		header = f'{tr("Username")}: {username}\n'

		password = get_password(tr('Password'), header=header, allow_skip=True)

		if not password:
			return None

		header += f'{tr("Password")}: {password.hidden()}\n\n'
		header += str(tr('Should "{}" be a superuser (sudo)?\n')).format(username)

		group = MenuItemGroup.yes_no()
		group.focus_item = MenuItem.yes()

		result = SelectMenu[bool](
			group,
			header=header,
			alignment=Alignment.CENTER,
			columns=2,
			orientation=Orientation.HORIZONTAL,
			search_enabled=False,
			allow_skip=False,
		).run()

		match result.type_:
			case ResultType.Selection:
				sudo = result.item() == MenuItem.yes()
			case _:
				raise ValueError('Unhandled result type')

		return User(username, password, sudo)


def ask_for_additional_users(prompt: str = '', defined_users: list[User] = []) -> list[User]:
	users = UserList(prompt, defined_users).run()
	return users
