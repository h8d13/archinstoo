# The kernel menu's escape hatch: a typed package name (a board kernel such as
# linux-rpi5) joins the stock picks, and stays selectable on the next visit.
from typing import TYPE_CHECKING

import pytest

from archinstoo.lib.interactions import system_conf
from archinstoo.lib.models.kernel import kernel_names_error
from archinstoo.lib.pm import packages
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


# what the fake repos carry
_REPOS = {'linux', 'linux-lts', 'linux-zen', 'linux-rpi5', 'linux-mainline'}


def _pick(monkeypatch: pytest.MonkeyPatch, picks: list[str], answers: list[str | None] | None = None) -> list[tuple[str, str | None]]:
	# answers are replayed one per prompt; returns (header, prefill) per
	# prompt shown, so a test can assert none was or what was re-asked
	prompts: list[tuple[str, str | None]] = []
	queue = list(answers or [])

	def fake_prompt(_title: str, header: str, preset: str | None, *_: object) -> str | None:
		prompts.append((header, preset))
		return queue.pop(0)

	monkeypatch.setattr(system_conf, 'SelectMenu', FakeMenu)
	monkeypatch.setattr(FakeMenu, 'picks', picks, raising=False)
	monkeypatch.setattr(system_conf, 'prompt_text', fake_prompt)
	monkeypatch.setattr(system_conf, 'missing_packages', lambda names: [n for n in names if n not in _REPOS])
	return prompts


def test_stock_pick_skips_the_prompt(monkeypatch: pytest.MonkeyPatch) -> None:
	prompts = _pick(monkeypatch, ['linux', 'linux-lts'])

	assert system_conf.select_kernel(['linux']) == ['linux', 'linux-lts']
	assert prompts == []


def test_typed_names_join_the_picks(monkeypatch: pytest.MonkeyPatch) -> None:
	_pick(monkeypatch, ['linux', system_conf._TYPE_KERNEL], ['linux-rpi5 linux'])

	assert system_conf.select_kernel([]) == ['linux', 'linux-rpi5']


def test_skipped_prompt_keeps_the_ticked(monkeypatch: pytest.MonkeyPatch) -> None:
	_pick(monkeypatch, ['linux-zen', system_conf._TYPE_KERNEL], [None])

	assert system_conf.select_kernel([]) == ['linux-zen']


def test_unknown_name_is_asked_again(monkeypatch: pytest.MonkeyPatch) -> None:
	# a typo never reaches pacstrap: the found names stay in the field
	prompts = _pick(monkeypatch, [system_conf._TYPE_KERNEL], ['linux-rpi5 linux-rpi6', 'linux-rpi5 linux-mainline'])

	assert system_conf.select_kernel([]) == ['linux-rpi5', 'linux-mainline']
	(_, first), (header, second) = prompts
	assert first is None
	assert second == 'linux-rpi5'
	assert 'Not found in the repositories: linux-rpi6' in header


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


@pytest.mark.parametrize(
	('listing', 'missing'),
	[
		({'linux': None, 'linux-rpi5': None}, ['linux-rpi6']),
		# offline or a failed sync lists nothing: nothing to check against
		({}, []),
	],
)
def test_missing_packages(monkeypatch: pytest.MonkeyPatch, listing: dict[str, None], missing: list[str]) -> None:
	monkeypatch.setattr(packages, 'list_available_packages', lambda: listing)

	assert packages.missing_packages(['linux', 'linux-rpi5', 'linux-rpi6']) == missing
