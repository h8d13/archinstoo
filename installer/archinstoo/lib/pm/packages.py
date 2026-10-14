from dataclasses import fields
from functools import lru_cache

from archinstoo.lib.hardware import SysInfo
from archinstoo.lib.models.packages import AvailablePackage, PackageGroup
from archinstoo.lib.output import debug
from archinstoo.lib.pm.dnf import Dnf

# dnf info labels -> AvailablePackage fields; the rest of its output is dropped
_INFO_FIELDS = {
	'Name': 'name',
	'Version': 'version',
	'Release': 'release',
	'Architecture': 'architecture',
	'Download size': 'download_size',
	'Installed size': 'installed_size',
	'Repository': 'repository',
	'Summary': 'summary',
	'URL': 'url',
	'License': 'license',
	'Description': 'description',
}


def _stub(repo: str, name: str, version: str) -> AvailablePackage:
	defaults = {f.name: '' for f in fields(AvailablePackage)}
	defaults.update({'repository': repo, 'name': name, 'version': version})
	return AvailablePackage(**defaults)


def _parse_info(text: str) -> list[dict[str, str]]:
	# blocks of `Label : value`; a blank label continues the field above
	# (wrapped descriptions)
	blocks: list[dict[str, str]] = []
	key: str | None = None
	for line in text.splitlines():
		label, sep, value = line.partition(':')
		if not sep:
			continue
		label = label.strip()
		if label == 'Name':
			blocks.append({})
		if not blocks:
			continue
		if label in _INFO_FIELDS:
			key = _INFO_FIELDS[label]
			blocks[-1][key] = value.strip()
		elif not label and key:
			blocks[-1][key] += ' ' + value.strip()
		else:
			key = None
	return blocks


def enrich_package_info(pkg: AvailablePackage, prefetch: list[AvailablePackage] | None = None) -> None:
	to_enrich = [p for p in (pkg, *(prefetch or [])) if not p.summary]
	if not to_enrich:
		return

	by_name = {p.name: p for p in to_enrich}
	try:
		out = Dnf.run(['info', '--available', '-q', *by_name]).decode()
	except Exception as e:
		debug(f'Failed to enrich package info: {e}')
		return

	for block in _parse_info(out):
		if target := by_name.get(block.get('name', '')):
			for key, value in block.items():
				setattr(target, key, value)


@lru_cache
def list_available_packages() -> dict[str, AvailablePackage]:
	# every enabled repo, latest build per name, this arch or noarch: the
	# set dnf would install from
	packages: dict[str, AvailablePackage] = {}
	try:
		out = Dnf.run([
			'repoquery', '--available', '--latest-limit=1', '-q',
			f'--arch={SysInfo.arch()},noarch',
			'--queryformat', r'%{repoid} %{name} %{evr}\n',
		]).decode()  # fmt: skip
	except Exception as e:
		debug(f'Failed to list available packages: {e}')
		return packages

	for line in out.splitlines():
		parts = line.split()
		if len(parts) == 3:
			packages.setdefault(parts[1], _stub(*parts))
	return packages


@lru_cache
def list_package_groups() -> dict[str, PackageGroup]:
	# comps groups install as @<id>, which is how they are listed too
	groups: dict[str, PackageGroup] = {}
	try:
		out = Dnf.run(['group', 'list', '--hidden', '-q']).decode()
	except Exception as e:
		debug(f'Failed to list package groups: {e}')
		return groups

	for line in out.splitlines():
		# ID  Name (may hold spaces)  Installed (yes/no), under one header row
		parts = line.split(None, 1)
		if len(parts) != 2 or parts[0] == 'ID':
			continue
		name = parts[1].rsplit(None, 1)[0]
		groups[f'@{parts[0]}'] = PackageGroup(f'@{parts[0]}', name)
	return groups


def missing_packages(names: list[str]) -> list[str]:
	# names the repos lack. No listing at all (offline, failed refresh)
	# checks nothing: the install still reports a bad name
	available = list_available_packages()
	if not available:
		debug('No package listing, skipping the repository check')
		return []
	return [n for n in names if n not in available and n not in list_package_groups()]
