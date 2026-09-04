# Drift guard for schema.toml.
#
# schema.toml is generated from the installer's own package definitions by
# lib/schema_gen.py, so the mappings cannot disagree with the install: they are
# the same objects. What can still go wrong is the file going stale, a package
# growing in a codepath no section reaches, or the tools that read the file
# (scripts/_resolve.py, nvchecker/NVGEN) losing track of a section.
#
# So the checks here are:
#   - the committed file is what the generator produces right now
#   - every package literal anywhere in the package is claimed by some section
#   - every option set the installer offers has a section covering it
#   - _resolve reads every section, and NVGEN still tracks what it yields

import ast
import importlib.machinery
import importlib.util
import tomllib
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from archinstoo.default_profiles.desktops import SeatAccess
from archinstoo.lib import installer, schema, schema_gen
from archinstoo.lib.hardware import CpuVendor, GfxPackage
from archinstoo.lib.models.application import (
	Audio,
	Firewall,
	PowerManagement,
	Security,
)
from archinstoo.lib.models.firmware import FirmwareType, FirmwareVendor
from archinstoo.lib.models.kernel import Kernel
from archinstoo.lib.pm import groups
from archinstoo.lib.schema import SCHEMA, SCHEMA_PATH
from archinstoo.scripts import _resolve

if TYPE_CHECKING:
	from enum import Enum
	from types import ModuleType


def test_committed_schema_is_current() -> None:
	# the one check the generated file exists for: everything below only
	# matters because this can be regenerated and diffed
	assert SCHEMA_PATH.read_text() == schema_gen.render(), f'{SCHEMA_PATH.name} is stale, run `python -m archinstoo --script schema`'


def test_every_section_is_a_table() -> None:
	# a top-level `key = [...]` written after the first [header] silently nests
	# under it, which is why the generator emits tables only
	for key, section in SCHEMA.items():
		assert isinstance(section, dict), f'schema[{key!r}] is not a table'


# -- option sets -------------------------------------------------------------
#
# Most sections are built by iterating an enum, so their keys match by
# construction and need no test. These are the ones the generator spells out
# member by member, where a new option can be forgotten.

_EXACT_SECTIONS: dict[str, type[Enum]] = {
	'firmware': FirmwareType,
	'audio': Audio,
	'firewalls': Firewall,
	'power_management': PowerManagement,
	'security': Security,
}


@pytest.mark.parametrize(('key', 'enum'), _EXACT_SECTIONS.items(), ids=list(_EXACT_SECTIONS))
def test_exact_sections(key: str, enum: type[Enum]) -> None:
	schema_keys = set(SCHEMA[key])
	enum_values = {e.value for e in enum}
	assert schema_keys == enum_values, (
		f'schema[{key!r}] options drifted from {enum.__name__}: '
		f'schema-only={sorted(schema_keys - enum_values)} '
		f'code-only={sorted(enum_values - schema_keys)}'
	)


# -- reverse cover -----------------------------------------------------------


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
	# section claims is invisible to count, size and nvchecker
	known = schema.package_names(SCHEMA)
	missing = {name: sorted(where) for name, where in _installed_literals().items() if name not in known}
	assert not missing, f'packages installed by code that no schema section lists: {missing}'


# disk_encryption is never written to a saved config (the password would go
# with it), so nothing count or size can be handed reaches this
_NOT_READ = {'fido2'}


def test_resolve_reads_every_section() -> None:
	# a section nobody consumes silently does nothing. _resolve names them as
	# string literals, so read them back the same way
	source = Path(_resolve.__file__).read_text()
	unread = {key for key in SCHEMA if f"'{key}'" not in source}
	assert unread == _NOT_READ, f'sections _resolve.py never reads: {sorted(unread - _NOT_READ)}; exempted but now read: {sorted(_NOT_READ - unread)}'


# -- nvchecker/NVGEN ---------------------------------------------------------
#
# NVGEN tracks package versions from schema.toml plus the enums that hold
# package names the schema never sees (kernels, vendor firmware, driver extras,
# microcode, seat access). It parses those enums statically (ast) to stay
# importable without the archinstoo runtime, so the checks below are: the parse
# still matches the real enums, and the committed nvchecker.toml still covers
# what they yield.

_NVDIR = Path(__file__).parents[2] / 'nvchecker'

# enum NVGEN reads -> live class, per PKG_ENUMS
_NVGEN_ENUMS: dict[str, type[Enum]] = {
	'Kernel': Kernel,
	'FirmwareVendor': FirmwareVendor,
	'GfxPackage': GfxPackage,
	'CpuVendor': CpuVendor,
	'SeatAccess': SeatAccess,
}


def _load_nvgen() -> ModuleType:
	# NVGEN is an extensionless script; import it by path. Everything but main()
	# is definitions, so importing has no side effects.
	path = _NVDIR / 'NVGEN'
	if not path.is_file():
		pytest.skip('nvchecker/NVGEN not present')

	loader = importlib.machinery.SourceFileLoader('nvgen', str(path))
	spec = importlib.util.spec_from_loader('nvgen', loader)
	assert spec is not None
	module = importlib.util.module_from_spec(spec)
	loader.exec_module(module)
	return module


def test_nvgen_enum_paths_resolve() -> None:
	nvgen = _load_nvgen()
	names = [class_name for _, class_name, _ in nvgen.PKG_ENUMS]
	assert names == list(_NVGEN_ENUMS), f'NVGEN PKG_ENUMS drifted from the enums under test: {names}'
	for path, class_name, _ in nvgen.PKG_ENUMS:
		assert path.is_file(), f'NVGEN points {class_name} at a missing file: {path}'


def test_nvgen_enum_parse_matches_code() -> None:
	# guards the static parse: a member turned into a computed value, or an enum
	# moved to another module, would silently drop packages from tracking.
	# private members (CpuVendor._Unknown) are skipped by both sides on purpose
	nvgen = _load_nvgen()
	for path, class_name, _ in nvgen.PKG_ENUMS:
		parsed = nvgen.enum_values(path, class_name)
		live = {e.value for e in _NVGEN_ENUMS[class_name] if not e.name.startswith('_')}
		assert parsed == live, f'NVGEN parse of {class_name} drifted: parsed-only={sorted(parsed - live)} code-only={sorted(live - parsed)}'


def test_nvgen_toml_tracks_code_packages() -> None:
	# the generated toml is committed; re-run `./NVGEN gen` when an enum changes
	nvgen = _load_nvgen()
	toml_path = _NVDIR / 'nvchecker.toml'
	if not toml_path.is_file():
		pytest.skip('nvchecker/nvchecker.toml not generated')

	tracked = set(tomllib.loads(toml_path.read_text())) - {'__config__'}
	missing = sorted(nvgen.code_packages() - tracked)
	assert not missing, f'nvchecker.toml is stale, run `./NVGEN gen`: missing {missing}'


def test_nvgen_does_not_track_profile_names_as_packages() -> None:
	# `profiles` entries name profiles, not packages; version tracking has to
	# skip them or nvchecker looks up things that are not in any repo
	nvgen = _load_nvgen()
	names = nvgen.extract_schema_packages(SCHEMA, {})
	profile_only = {p for p in SCHEMA['xorg_profiles']['profiles'] if p not in schema.package_names(SCHEMA)}
	assert not (names & profile_only), f'NVGEN would track profile names: {sorted(names & profile_only)}'


def test_nvgen_shares_the_installer_modules() -> None:
	# NVGEN path-loads lib/schema.py and lib/pm/groups.py rather than keeping
	# its own loader and group expansion; those copies are what drifted before.
	# also proves both modules stay loadable without the archinstoo runtime
	nvgen = _load_nvgen()
	assert Path(schema.__file__) == nvgen.SCHEMA_MODULE, f'NVGEN loads a different schema module: {nvgen.SCHEMA_MODULE}'
	assert Path(groups.__file__) == nvgen.GROUPS_MODULE, f'NVGEN loads a different groups module: {nvgen.GROUPS_MODULE}'
	assert nvgen.schema_mod.SCHEMA == SCHEMA
	assert nvgen.groups_mod.parse(_SGG_OUTPUT) == groups.parse(_SGG_OUTPUT)


# -- pacman groups (lib/pm/groups.py) ----------------------------------------
#
# Some schema entries are groups, not packages. pactree/expac report them as
# unknown, so resolve_deps() expands them first or the members and their whole
# closure vanish from the count and size estimates.

_SGG_OUTPUT = """mate caja
mate marco
xfce4-goodies xfburn

"""


def test_parse_reads_sgg_pairs() -> None:
	assert groups.parse(_SGG_OUTPUT) == {'mate': {'caja', 'marco'}, 'xfce4-goodies': {'xfburn'}}


def test_expand_replaces_groups_with_members(monkeypatch: pytest.MonkeyPatch) -> None:
	monkeypatch.setattr(groups, 'sync', lambda: groups.parse(_SGG_OUTPUT))

	# 'nano' is a package, not a group, and must survive untouched
	assert groups.expand({'mate', 'xfce4-goodies', 'nano'}) == {'caja', 'marco', 'xfburn', 'nano'}


def test_resolve_uses_the_shared_modules() -> None:
	# _resolve must not grow its own copies again
	resolve_ns = vars(_resolve)
	assert resolve_ns['expand'] is groups.expand
	assert resolve_ns['SCHEMA'] is SCHEMA


def test_schema_group_entries_are_not_treated_as_packages() -> None:
	# guards the inputs the expansion exists for: these schema profile entries
	# are pacman groups today, so they must never be counted as single packages
	known_groups = {'budgie', 'cosmic', 'deepin', 'lxqt', 'mate', 'mate-extra', 'xfce4', 'xfce4-goodies'}
	schema_entries = {p for pkgs in SCHEMA['profiles'].values() for p in pkgs}
	present = known_groups & schema_entries
	assert present, 'no group entries left in schema profiles; drop expand() if that is intentional'
