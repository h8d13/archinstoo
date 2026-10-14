from typing import override

from archinstoo.lib.menu.abstract_menu import AbstractSubMenu
from archinstoo.lib.models.dnf import PARALLEL_DOWNLOADS_RANGE, DnfConfiguration
from archinstoo.lib.tui.menu_item import MenuItem, MenuItemGroup
from archinstoo.lib.tui.prompts import prompt_text, prompt_yes_no


class DnfMenu(AbstractSubMenu[DnfConfiguration]):
	def __init__(self, preset: DnfConfiguration | None = None) -> None:
		self._dnf_config = preset or DnfConfiguration()
		self._item_group = MenuItemGroup(self._define_menu_options(), sort_items=False, checkmarks=True)
		super().__init__(self._item_group, config=self._dnf_config, allow_reset=True)

	def _define_menu_options(self) -> list[MenuItem]:
		return [
			MenuItem(
				text='Weak dependencies',
				action=select_weak_deps,
				value=self._dnf_config.install_weak_deps,
				preview_action=lambda item: f'Install recommended packages: {"Enabled" if item.value else "Disabled"}',
				key='install_weak_deps',
			),
			MenuItem(
				text='Parallel downloads',
				action=select_parallel_downloads,
				value=self._dnf_config.max_parallel_downloads,
				preview_action=lambda item: f'Parallel downloads: {item.value or "dnf default (3)"}',
				key='max_parallel_downloads',
			),
		]

	@override
	def run(self, additional_title: str | None = None) -> DnfConfiguration:
		super().run(additional_title=additional_title)
		return self._dnf_config


def select_weak_deps(preset: bool) -> bool:
	header = 'Install the packages dnf only recommends (weak dependencies)?\n'
	header += 'Applies to everything after the base, which always takes them (systemd needs its\n'
	header += 'recommended dbus and libraries); the kernel never pulls them in either way.\n'
	choice = prompt_yes_no(header, preset)
	return preset if choice is None else choice


def _parallel_error(text: str | None) -> str | None:
	if not text:
		return None
	if not text.isdigit() or int(text) not in PARALLEL_DOWNLOADS_RANGE:
		return 'Enter a number from 1 to 20'
	return None


def select_parallel_downloads(preset: int | None) -> int | None:
	header = 'Packages dnf downloads at once (1-20). Leave empty for dnf default.\n'
	text = prompt_text('Parallel downloads', header, str(preset) if preset else None, _parallel_error)
	if text is None:
		return preset
	return int(text) if text else None
