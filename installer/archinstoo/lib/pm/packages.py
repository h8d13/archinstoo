import contextlib
from dataclasses import fields
from functools import lru_cache

from archinstoo.lib.models.packages import AvailablePackage, LocalPackage
from archinstoo.lib.output import debug
from archinstoo.lib.pacman import Pacman


def _create_package_stub(repo: str, name: str, version: str) -> AvailablePackage:
	defaults = {f.name: '' for f in fields(AvailablePackage)}
	defaults.update({'repository': repo, 'name': name, 'version': version})
	return AvailablePackage(**defaults)


def _update_package(pkg: AvailablePackage, detailed: AvailablePackage) -> None:
	for f in fields(AvailablePackage):
		setattr(pkg, f.name, getattr(detailed, f.name))


def enrich_package_info(pkg: AvailablePackage, prefetch: list[AvailablePackage] = []) -> None:
	# Collect packages that need enrichment
	to_enrich = []
	if not pkg.description:
		to_enrich.append(pkg)

	to_enrich.extend(p for p in prefetch if not p.description)

	if not to_enrich:
		return

	# Batch fetch with single pacman call
	with contextlib.suppress(Exception):
		pkg_names = ' '.join(p.name for p in to_enrich)
		current_package = []

		for line in Pacman.run(f'-Si {pkg_names}'):
			dec_line = line.decode().rstrip()
			current_package.append(dec_line)

			if dec_line.startswith('Validated') and current_package:
				detailed = _parse_package_output(current_package, AvailablePackage)
				# Find matching package and update it
				for p in to_enrich:
					if p.name == detailed.name:
						_update_package(p, detailed)
						break
				current_package = []


@lru_cache
def list_available_packages() -> dict[str, AvailablePackage]:
	# Every repo section in the live pacman.conf, no explicit list: the conf is
	# already the truth pacstrap installs from (PacmanConfig.apply() writes it
	# before this menu opens), so a host's own repos (cachyos, multilib, ...)
	# show up without archinstoo having to know their names.
	packages: dict[str, AvailablePackage] = {}

	try:
		Pacman.run('-Sy')
	except Exception as e:
		debug(f'Failed to sync Arch Linux package database: {e}')

	try:
		# -Sl walks repos in conf order, so setdefault (not assignment) keeps the
		# same winner pacman would pick when a name exists in more than one repo
		for line in Pacman.run('-Sl'):
			parts = line.decode().strip().split()
			if len(parts) >= 3:
				packages.setdefault(parts[1], _create_package_stub(parts[0], parts[1], parts[2]))
	except Exception as e:
		debug(f'Failed to list available packages: {e}')

	return packages


@lru_cache(maxsize=128)
def _normalize_key_name(key: str) -> str:
	return key.strip().lower().replace(' ', '_')


def _parse_package_output[PackageType: (AvailablePackage, LocalPackage)](
	package_meta: list[str],
	cls: type[PackageType],
) -> PackageType:
	package: dict[str, str] = {}
	valid_fields = {f.name for f in fields(cls)}
	current_key: str | None = None

	for line in package_meta:
		# indented lines continue the previous field's value (wrapped
		# descriptions and multi-entry fields like Optional Deps)
		if line and line[0] in ' \t':
			if current_key:
				package[current_key] += ' ' + line.strip()
			continue

		if ':' in line:
			key, value = line.split(':', 1)
			key = _normalize_key_name(key)
			if key in valid_fields:
				package[key] = value.strip()
				current_key = key
			else:
				current_key = None

	return cls(**package)
