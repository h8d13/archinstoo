# Custom repo names become pacman.conf section headers, so they must be unique
# and stay clear of the sections pacman and the Arch repos own. List order is
# the order they are written, which pacman reads as priority.

import pytest

from archinstoo.lib.models.mirrors import CustomRepository, SignCheck, SignOption
from archinstoo.lib.pm.mirrors import CustomMirrorRepositoriesList


def _repo(name: str, priority: bool = False) -> CustomRepository:
	return CustomRepository(name, f'https://{name}.example/$arch', SignCheck.Never, SignOption.TrustAll, priority)


@pytest.mark.parametrize('name', ['core', 'extra', 'options', 'multilib-testing', 'Core'])
def test_reserved_name_rejected(name: str) -> None:
	assert CustomRepository.name_error(name, []) is not None


@pytest.mark.parametrize('name', ['vrch', 'VRCH'])
def test_taken_name_rejected(name: str) -> None:
	assert CustomRepository.name_error(name, ['vrch']) is not None


@pytest.mark.parametrize('name', ['', '   '])
def test_empty_name_rejected(name: str) -> None:
	assert CustomRepository.name_error(name, []) is not None


def test_free_name_accepted() -> None:
	assert CustomRepository.name_error('vrch', ['other']) is None


def test_config_with_duplicate_names_rejected() -> None:
	args = [_repo('vrch').json(), _repo('vrch').json()]

	with pytest.raises(ValueError, match='already exists'):
		CustomRepository.parse_args([dict(a) for a in args])


def test_config_with_reserved_name_rejected() -> None:
	with pytest.raises(ValueError, match='reserved'):
		CustomRepository.parse_args([dict(_repo('core').json())])


def _menu(monkeypatch: pytest.MonkeyPatch, data: list[CustomRepository], result: CustomRepository) -> tuple[CustomMirrorRepositoriesList, list[list[str]]]:
	# stands in for the prompts; records which names were off limits
	seen: list[list[str]] = []

	def fake_prompt(taken: list[str], preset: CustomRepository | None = None) -> CustomRepository:
		seen.append(taken)
		return result

	menu = CustomMirrorRepositoriesList(data)
	monkeypatch.setattr(menu, '_add_custom_repository', fake_prompt)
	return menu, seen


def test_add_appends_and_blocks_every_existing_name(monkeypatch: pytest.MonkeyPatch) -> None:
	data = [_repo('a'), _repo('b')]
	menu, seen = _menu(monkeypatch, data, _repo('c'))

	result = menu.handle_action(menu._actions[0], None, data)

	assert [r.name for r in result] == ['a', 'b', 'c']
	assert seen == [['a', 'b']]


def test_edit_keeps_slot_and_frees_own_name(monkeypatch: pytest.MonkeyPatch) -> None:
	data = [_repo('a'), _repo('b'), _repo('c')]
	edited = _repo('a', priority=True)
	menu, seen = _menu(monkeypatch, data, edited)

	result = menu.handle_action(menu._actions[1], data[0], data)

	assert result == [edited, data[1], data[2]]
	assert seen == [['b', 'c']]
