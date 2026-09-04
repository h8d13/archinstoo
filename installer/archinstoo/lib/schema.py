# schema.toml: where it lives and how to read it.
#
# The file is generated from the installer's own package definitions by
# lib/schema_gen.py, so nothing here should ever be hand-edited, used by various scripts.

import tomllib
from pathlib import Path
from typing import Any

SCHEMA_PATH = Path(__file__).parent.parent / 'schema.toml'

# an entry under this name holds profile names, not packages
PROFILE_KEY = 'profiles'


def load(path: Path = SCHEMA_PATH) -> dict[str, Any]:
	with path.open('rb') as f:
		result: dict[str, Any] = tomllib.load(f)
	return result


def package_names(schema: dict[str, Any]) -> set[str]:
	# every package the schema names, for callers that want the set
	names: set[str] = set()

	for section in schema.values():
		for name, values in section.items():
			if name == PROFILE_KEY:
				continue
			# a nested section (compositors) is one table per profile
			for pkgs in values.values() if isinstance(values, dict) else [values]:
				names.update(pkgs)

	return names


SCHEMA = load()
