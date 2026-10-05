# The kernel menu's escape hatch: a typed package name (a board kernel such as
# linux-rpi5) joins the stock picks, and stays selectable on the next visit.
from typing import TYPE_CHECKING

import pytest

from archinstoo.lib.interactions import system_conf
from archinstoo.lib.models.kernel import kernel_names_error
from archinstoo.lib.tui.result import Result, ResultType

if TYPE_CHECKING:
	from archinstoo.lib.tui.menu_item import MenuItemGroup


class FakeMenu:
	# stands in for SelectMenu: ticks the values in `picks` and keeps the
	# group it was built with, no terminal
	picks: list[str]
	group: MenuItemGroup

	def __init__(self, group: MenuItemGroup, **_: object) -> None:
		FakeMenu.group = group

	@classmethod
	def __class_getitem__(cls, _: object) -> type[FakeMenu]:
		return cls

	def run(self) -> Result[str]:
		items = [i for i in FakeMenu.group.items if i.value in FakeMenu.picks]
		return Result(ResultType.Selection, items)


def _pick(monkeypatch: pytest.MonkeyPatch, picks: list[str], typed: str | None = None) -> list[str]:
	# returns the prompts shown, so a test can assert none was
	prompts: list[str] = []

	def fake_prompt(title: str, *_: object, **__: object) -> str | None:
		prompts.append(title)
		return typed

	monkeypatch.setattr(system_conf, 'SelectMenu', FakeMenu)
	monkeypatch.setattr(FakeMenu, 'picks', picks, raising=False)
	monkeypatch.setattr(system_conf, 'prompt_text', fake_prompt)
	return prompts


def test_stock_pick_skips_the_prompt(monkeypatch: pytest.MonkeyPatch) -> None:
	prompts = _pick(monkeypatch, ['linux', 'linux-lts'])

	assert system_conf.select_kernel(['linux']) == ['linux', 'linux-lts']
	assert prompts == []


def test_typed_names_join_the_picks(monkeypatch: pytest.MonkeyPatch) -> None:
	_pick(monkeypatch, ['linux', system_conf._TYPE_KERNEL], typed='linux-rpi5 linux')

	assert system_conf.select_kernel([]) == ['linux', 'linux-rpi5']


def test_skipped_prompt_keeps_the_ticked(monkeypatch: pytest.MonkeyPatch) -> None:
	_pick(monkeypatch, ['linux-zen', system_conf._TYPE_KERNEL], typed=None)

	assert system_conf.select_kernel([]) == ['linux-zen']


def test_typed_name_stays_tickable(monkeypatch: pytest.MonkeyPatch) -> None:
	# a config's board kernel used to be dropped on reopening the menu
	_pick(monkeypatch, ['linux-rpi5'])

	assert system_conf.select_kernel(['linux-rpi5']) == ['linux-rpi5']
	assert [i.value for i in FakeMenu.group.selected_items] == ['linux-rpi5']


@pytest.mark.parametrize(
	('text', 'ok'),
	[
		('linux-rpi5', True),
		('linux-mainline linux-rpi5', True),
		('linux-g14 linux_custom+1', True),
		('', False),
		('   ', False),
		('Linux-RPi5', False),
		('-linux', False),
		('linux;rm', False),
	],
)
def test_kernel_name_check(text: str, ok: bool) -> None:
	assert (kernel_names_error(text) is None) is ok
