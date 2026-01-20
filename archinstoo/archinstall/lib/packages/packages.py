from dataclasses import fields
from functools import lru_cache

from ..exceptions import SysCallError
from ..models.packages import AvailablePackage, LocalPackage, Repository
from ..output import debug
from ..pacman import Pacman


def installed_package(package: str) -> LocalPackage | None:
	try:
		package_info = []
		for line in Pacman.run(f'-Q --info {package}'):
			package_info.append(line.decode().strip())

		return _parse_package_output(package_info, LocalPackage)
	except SysCallError:
		pass

	return None


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

	for p in prefetch:
		if not p.description:
			to_enrich.append(p)

	if not to_enrich:
		return

	# Batch fetch with single pacman call
	try:
		pkg_names = ' '.join(p.name for p in to_enrich)
		current_package = []

		for line in Pacman.run(f'-Si {pkg_names}'):
			dec_line = line.decode().strip()
			current_package.append(dec_line)

			if dec_line.startswith('Validated'):
				if current_package:
					detailed = _parse_package_output(current_package, AvailablePackage)
					# Find matching package and update it
					for p in to_enrich:
						if p.name == detailed.name:
							_update_package(p, detailed)
							break
					current_package = []
	except Exception:
		pass


@lru_cache
def list_available_packages(
	repositories: tuple[Repository, ...],
) -> dict[str, AvailablePackage]:
	"""
	Returns a list of all available packages in the database
	"""
	packages: dict[str, AvailablePackage] = {}

	try:
		Pacman.run('-Sy')
	except Exception as e:
		debug(f'Failed to sync Arch Linux package database: {e}')

	# Load package stubs from repositories
	for repo in repositories:
		try:
			for line in Pacman.run(f'-Sl {repo.value}'):
				parts = line.decode().strip().split()
				if len(parts) >= 3:
					packages[parts[1]] = _create_package_stub(parts[0], parts[1], parts[2])
		except Exception as e:
			debug(f'Failed to list packages from {repo.value}: {e}')

	return packages


@lru_cache(maxsize=128)
def _normalize_key_name(key: str) -> str:
	return key.strip().lower().replace(' ', '_')


def _parse_package_output[PackageType: (AvailablePackage, LocalPackage)](
	package_meta: list[str],
	cls: type[PackageType],
) -> PackageType:
	package = {}
	valid_fields = {f.name for f in fields(cls)}

	for line in package_meta:
		if ':' in line:
			key, value = line.split(':', 1)
			key = _normalize_key_name(key)
			if key in valid_fields:
				package[key] = value.strip()

	return cls(**package)
