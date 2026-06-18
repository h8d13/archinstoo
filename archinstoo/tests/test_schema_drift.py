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
#              (profiles, gfx drivers, and the à-la-carte enum categories)

import pytest

from archinstoo.lib.hardware import GfxDriver
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
from archinstoo.lib.models.network import NicType
from archinstoo.lib.models.users import Shell
from archinstoo.lib.profile.base import GreeterType, ProfileType
from archinstoo.lib.profile.profiles_handler import ProfileHandler
from archinstoo.scripts._resolve import SCHEMA

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
	'greeters': GreeterType,
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
def test_exact_sections(key: str, enum: type) -> None:
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


def test_gfx_driver_packages_match() -> None:
	# base package set only; gfx_packages() adds kernel/GPU-conditional extras
	# at runtime (dkms, vulkan-intel/radeon) which the static schema can't model
	for driver in GfxDriver:
		code_pkgs = sorted(p.value for p in driver.gfx_packages(None))
		schema_pkgs = sorted(SCHEMA['gfx_drivers'][driver.value])
		assert schema_pkgs == code_pkgs, f'gfx driver {driver.value!r} packages drifted: schema={schema_pkgs} code={code_pkgs}'


@pytest.mark.parametrize('enum', _ONE_TO_ONE_SECTIONS, ids=lambda e: e.__name__)
def test_one_to_one_categories(enum: type) -> None:
	# install path is [tool.value for tool in tools], so each option maps to
	# exactly itself; the section is found by matching the enum's value set
	section = next(k for k, v in SCHEMA.items() if isinstance(v, dict) and set(v) == {e.value for e in enum})
	for member in enum:
		assert SCHEMA[section][member.value] == [member.value], f'{section}[{member.value!r}] should map to itself, got {SCHEMA[section][member.value]}'
