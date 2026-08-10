# Drift guard for schema.jsonc.
#
# schema.jsonc duplicates the package mappings that actually live in the
# install codepaths (profiles, app categories, drivers, greeters). The count
# and size scripts read the schema instead of running the installer, so a
# package added to a profile or an option renamed in an enum can silently
# drift out of those estimates. These tests import the real codepaths and
# assert the schema still matches.
#
# Three relationships are checked:
#   - exact:   schema keys == enum values (option set must match 1:1)
#   - subset:  schema keys subseteq enum values (some options need no package,
#              e.g. bash/ext4 are handled by base and deliberately omitted)
#   - content: package lists match, where the code exposes them statically
#              (profiles, gfx drivers, greeters, and the enum categories)

import ast
import importlib.machinery
import importlib.util
import inspect
import textwrap
import tomllib
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from archinstoo.default_profiles.desktops import SeatAccess
from archinstoo.lib import schema
from archinstoo.lib.hardware import CpuVendor, GfxDriver, GfxPackage, _sys_info
from archinstoo.lib.models.application import (
	Audio,
	DevTool,
	Editor,
	Firewall,
	Language,
	Management,
	Monitor,
	PowerManagement,
	Security,
)
from archinstoo.lib.models.authentication import PrivilegeEscalation
from archinstoo.lib.models.bootloader import Bootloader
from archinstoo.lib.models.device import FilesystemType, SnapshotType
from archinstoo.lib.models.firmware import FirmwareVendor
from archinstoo.lib.models.kernel import Kernel
from archinstoo.lib.models.network import NicType
from archinstoo.lib.models.users import Shell
from archinstoo.lib.pm import groups
from archinstoo.lib.profile.base import GreeterType, ProfileType
from archinstoo.lib.profile.profiles_handler import ProfileHandler
from archinstoo.scripts import _resolve
from archinstoo.scripts._resolve import SCHEMA

if TYPE_CHECKING:
	from enum import Enum
	from types import ModuleType

# leaf profile types map 1:1 to schema['profiles']; the rest (Desktop/Server/
# Xorg/Minimal) are abstract bases the handler also discovers
_LEAF_PROFILE_TYPES = {
	ProfileType.DesktopEnv,
	ProfileType.WindowMgr,
	ProfileType.ServerType,
}

# schema key -> enum whose values must exactly match the key set
_EXACT_SECTIONS = {
	'audio': Audio,
	'monitors': Monitor,
	'editors': Editor,
	'firewalls': Firewall,
	'power_management': PowerManagement,
	'security': Security,
	'languages': Language,
	'devtools': DevTool,
	'management': Management,
	'gfx_drivers': GfxDriver,
	'bootloaders': Bootloader,
	'privilege_escalation': PrivilegeEscalation,
	'snapshots': SnapshotType,
}

# sections that deliberately omit options needing no extra package; the synthetic
# set lists keys modelled by _resolve.py that have no enum counterpart
_SUBSET_SECTIONS = {
	'shells': (Shell, set()),
	'filesystem_tools': (FilesystemType, set()),
	'network': (NicType, {'nm-desktop-extra'}),
}

# categories the installer expands as [tool.value for tool in tools]: each
# schema entry must therefore be the option name mapped to itself
_ONE_TO_ONE_SECTIONS = (Management, Language, DevTool)


@pytest.mark.parametrize(('key', 'enum'), _EXACT_SECTIONS.items(), ids=list(_EXACT_SECTIONS))
def test_exact_sections(key: str, enum: type[Enum]) -> None:
	schema_keys = set(SCHEMA[key])
	enum_values = {e.value for e in enum}
	assert schema_keys == enum_values, (
		f'schema[{key!r}] options drifted from {enum.__name__}: '
		f'schema-only={sorted(schema_keys - enum_values)} '
		f'code-only={sorted(enum_values - schema_keys)}'
	)


@pytest.mark.parametrize('key', _SUBSET_SECTIONS, ids=str)
def test_subset_sections(key: str) -> None:
	enum, synthetic = _SUBSET_SECTIONS[key]
	schema_keys = set(SCHEMA[key]) - synthetic
	enum_values = {e.value for e in enum}
	assert schema_keys <= enum_values, f'schema[{key!r}] has options absent from {enum.__name__}: {sorted(schema_keys - enum_values)}'


def test_profiles_match() -> None:
	profiles = {p.name: sorted(p.packages) for p in ProfileHandler().profiles if p.profile_type in _LEAF_PROFILE_TYPES}
	schema_profiles = {k: sorted(v) for k, v in SCHEMA['profiles'].items()}

	assert set(schema_profiles) == set(profiles), (
		f'profile set drifted: schema-only={sorted(set(schema_profiles) - set(profiles))} code-only={sorted(set(profiles) - set(schema_profiles))}'
	)
	for name, code_pkgs in profiles.items():
		assert schema_profiles[name] == code_pkgs, f'profile {name!r} packages drifted: schema={schema_profiles[name]} code={code_pkgs}'


def test_dms_compositors_match() -> None:
	# the dms "profiles" entry bakes in the niri default; _resolve.py swaps
	# per-compositor sets via schema['dms_compositors'] when the saved config
	# carries a dms_compositor selection
	from archinstoo.default_profiles.desktops.dms import _COMPOSITOR_PACKAGES

	code = {k: sorted(v) for k, v in _COMPOSITOR_PACKAGES.items()}
	schema = {k: sorted(v) for k, v in SCHEMA['dms_compositors'].items()}
	assert schema == code, f'dms compositor packages drifted: schema={schema} code={code}'


def test_gfx_driver_packages_match(monkeypatch: pytest.MonkeyPatch) -> None:
	# base package set only; gfx_packages() adds kernel/GPU-conditional extras
	# at runtime (dkms, vulkan-intel/radeon) which the static schema can't model.
	# MesaOpenSource probes the host GPU via lspci; pin detection to empty so
	# the base set comes back on any machine running the tests
	monkeypatch.setattr(_sys_info, 'graphics_devices', {})
	for driver in GfxDriver:
		code_pkgs = sorted(p.value for p in driver.gfx_packages(None))
		schema_pkgs = sorted(SCHEMA['gfx_drivers'][driver.value])
		assert schema_pkgs == code_pkgs, f'gfx driver {driver.value!r} packages drifted: schema={schema_pkgs} code={code_pkgs}'


def _greeter_packages() -> dict[str, list[str]]:
	# install_greeter() picks packages with a match over GreeterType; each arm
	# assigns a literal `packages = [...]`. Parse those arms statically instead
	# of running install_greeter (which needs a live Installer).
	src = textwrap.dedent(inspect.getsource(ProfileHandler.install_greeter))
	match = next(n for n in ast.walk(ast.parse(src)) if isinstance(n, ast.Match))

	out: dict[str, list[str]] = {}
	for case in match.cases:
		# only `case GreeterType.X:` arms name a member, a wildcard names nothing
		pattern = case.pattern
		if not isinstance(pattern, ast.MatchValue) or not isinstance(pattern.value, ast.Attribute):
			continue

		member = getattr(GreeterType, pattern.value.attr).value
		for stmt in case.body:
			if isinstance(stmt, ast.Assign) and any(getattr(t, 'id', None) == 'packages' for t in stmt.targets):
				out[member] = sorted(ast.literal_eval(stmt.value))
	return out


def test_greeter_packages_match() -> None:
	code = _greeter_packages()
	schema = {k: sorted(v) for k, v in SCHEMA['greeters'].items()}
	assert schema == code, (
		f'greeter packages drifted: schema-only={sorted(set(schema) - set(code))} '
		f'code-only={sorted(set(code) - set(schema))} '
		f'mismatched={ {k: (schema[k], code[k]) for k in schema.keys() & code.keys() if schema[k] != code[k]} }'
	)


@pytest.mark.parametrize('enum', _ONE_TO_ONE_SECTIONS, ids=lambda e: e.__name__)
def test_one_to_one_categories(enum: type[Enum]) -> None:
	# install path is [tool.value for tool in tools], so each option maps to
	# exactly itself; the section is found by matching the enum's value set
	section = next(k for k, v in SCHEMA.items() if isinstance(v, dict) and set(v) == {e.value for e in enum})
	for member in enum:
		assert SCHEMA[section][member.value] == [member.value], f'{section}[{member.value!r}] should map to itself, got {SCHEMA[section][member.value]}'


# -- nvchecker/NVGEN ---------------------------------------------------------
#
# NVGEN tracks package versions from schema.jsonc plus the enums that hold
# package names the schema never sees (kernels, vendor firmware, driver extras,
# microcode, seat access) - the non-schema sources _resolve.py reads. It parses
# those enums statically (ast) to stay importable without the archinstoo
# runtime, so the checks below are: the parse still matches the real enums, and
# the committed nvchecker.toml still covers what they yield.

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
	assert _resolve.expand is groups.expand
	assert _resolve.SCHEMA is SCHEMA


def test_schema_group_entries_are_not_treated_as_packages() -> None:
	# guards the inputs the expansion exists for: these schema profile entries
	# are pacman groups today, so they must never be counted as single packages
	known_groups = {'budgie', 'cosmic', 'deepin', 'lxqt', 'mate', 'mate-extra', 'xfce4', 'xfce4-goodies'}
	schema_entries = {p for pkgs in SCHEMA['profiles'].values() for p in pkgs}
	present = known_groups & schema_entries
	assert present, 'no group entries left in schema profiles; drop expand() if that is intentional'
