# schema.toml is the inventory of every package the installer can name;
# these keep it equal to the code that installs them

import ast
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from archinstoo.lib import installer, schema, schema_gen
from archinstoo.lib.models.applications import Audio, Firewall, PowerManagement, Security
from archinstoo.lib.models.firmware import FirmwareType
from archinstoo.lib.schema import SCHEMA, SCHEMA_PATH

if TYPE_CHECKING:
	from enum import Enum


def test_committed_schema_is_current() -> None:
	assert SCHEMA_PATH.read_text() == schema_gen.render(), f'{SCHEMA_PATH.name} is stale, run `python -m archinstoo --script schema`'


def test_sections_are_listed_in_install_order() -> None:
	# render() sorts by site regardless; this keeps the source readable top to
	# bottom as the install, so a reorder in guided.py is mirrored here
	listed = [s.key for s in schema_gen.SECTIONS]
	assert listed == [s.key for s in schema_gen.ordered()]


def test_every_section_is_a_table() -> None:
	# a top-level `key = [...]` written after the first [header] silently nests
	# under it, which is why the generator emits tables only
	for key, section in SCHEMA.items():
		assert isinstance(section, dict), f'schema[{key!r}] is not a table'


# the sections the generator spells out member by member, where a new option
# can be forgotten; the rest iterate their enum
_EXACT_SECTIONS: dict[str, type[Enum]] = {
	'firmware': FirmwareType,
	'audio': Audio,
	'firewalls': Firewall,
	'power_management': PowerManagement,
	'security': Security,
}


@pytest.mark.parametrize(('key', 'enum'), _EXACT_SECTIONS.items(), ids=list(_EXACT_SECTIONS))
def test_exact_sections(key: str, enum: type[Enum]) -> None:
	assert set(SCHEMA[key]) == {e.value for e in enum}


def _installed_literals() -> dict[str, set[str]]:
	# every package name the package installs outright, anywhere: handed to
	# add_additional_packages/strap, appended to _base_packages, or returned as
	# a literal list from a *_packages property. f-strings and enum lookups are
	# runtime values and drop out
	found: dict[str, set[str]] = {}

	def record(name: str, path: Path) -> None:
		found.setdefault(name, set()).add(str(path.relative_to(Path(installer.__file__).parents[1])))

	for path in sorted(Path(installer.__file__).parent.parent.rglob('*.py')):
		tree = ast.parse(path.read_text())

		consts = {
			target.id: node.value.value
			for node in ast.walk(tree)
			if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str)
			for target in node.targets
			if isinstance(target, ast.Name)
		}

		def literals(node: ast.expr, consts: dict[str, str] = consts) -> set[str]:
			if isinstance(node, ast.Constant) and isinstance(node.value, str):
				return {node.value}
			if isinstance(node, ast.Name):
				return {consts[node.id]} if node.id in consts else set()
			if isinstance(node, ast.List | ast.Tuple):
				return {name for elt in node.elts for name in literals(elt)}
			return set()

		for node in ast.walk(tree):
			# install calls
			if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
				installs = node.func.attr in ('add_additional_packages', 'strap') or (
					node.func.attr in ('append', 'extend') and getattr(node.func.value, 'attr', '') == '_base_packages'
				)
				if installs:
					for arg in node.args:
						for name in literals(arg):
							record(name, path)

			# `def <x>_packages(...)` returning a literal list. only a list or
			# tuple counts: menu helpers of the same shape return display text
			if isinstance(node, ast.FunctionDef) and (node.name == 'packages' or node.name.endswith('_packages')):
				for stmt in ast.walk(node):
					if isinstance(stmt, ast.Return) and isinstance(stmt.value, ast.List | ast.Tuple):
						for name in literals(stmt.value):
							record(name, path)

	return found


def test_every_installed_package_is_in_the_schema() -> None:
	# the reverse of the generator: a package some codepath grew that no
	# section claims is missing from the inventory
	known = schema.package_names(SCHEMA)
	missing = {name: sorted(where) for name, where in _installed_literals().items() if name not in known}
	assert not missing, f'packages installed by code that no schema section lists: {missing}'
