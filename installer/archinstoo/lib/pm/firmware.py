# Firmware packages this host needs: declared module firmware, owned per core's
# files db. Runtime-named firmware (SOF, tas2781, amdtee) goes undetected and
# btusb pulls every vendor's helper, so this narrows an install, FULL stays default

import fnmatch
import sys
from functools import cache

from archinstoo.lib.hardware import SysInfo
from archinstoo.lib.models.firmware import FIRMWARE_OPTDEPS, FULL_FIRMWARE, FirmwareConfiguration, FirmwareType, FirmwareVendor
from archinstoo.lib.output import debug
from archinstoo.lib.pm.tmpdb import TmpDB

_FIRMWARE_DIR = 'usr/lib/firmware/'

# catch-all for firmware no module declares
_SPLIT_BASELINE = frozenset({FirmwareVendor.OTHER})


@cache
def firmware_index() -> dict[str, str]:
	if '--offline' in sys.argv:
		debug('Offline: no files db, firmware detection off')
		return {}

	db = TmpDB(('core',))
	if not db.sync_files():
		return {}

	return {path.removeprefix(_FIRMWARE_DIR).removesuffix('.zst'): pkg for pkg, path in db.files() if path.startswith(_FIRMWARE_DIR)}


def owners(declared: set[str], index: dict[str, str]) -> set[str]:
	found: set[str] = set()
	for entry in declared:
		if any(c in entry for c in '*?['):
			found.update(index[path] for path in fnmatch.filter(index, entry))
		elif pkg := index.get(entry):
			found.add(pkg)
	return found


@cache
def _detected() -> frozenset[FirmwareVendor]:
	# before the index: a VM or a host declaring nothing never syncs
	if not (declared := SysInfo.declared_firmware()):
		return frozenset()

	members = {v.value: v for v in FirmwareVendor}
	found = owners(declared, firmware_index())

	for pkg in sorted(found - members.keys()):
		if pkg.startswith('linux-firmware-'):
			debug(f'Firmware split {pkg} is not a FirmwareVendor member')

	detected = frozenset(members[pkg] for pkg in found if pkg in members)
	debug(f'Firmware detected: {sorted(detected)} from {len(declared)} declared names')
	return detected


def detect_splits() -> list[FirmwareVendor]:
	return sorted(_detected() | _SPLIT_BASELINE)


def detect_optdeps() -> list[FirmwareVendor]:
	return sorted(_detected() & FIRMWARE_OPTDEPS)


def firmware_packages(config: FirmwareConfiguration) -> list[str]:
	match config.firmware_type:
		case FirmwareType.FULL:
			return [*FULL_FIRMWARE, *(v.value for v in detect_optdeps())]
		case FirmwareType.MINIMAL:
			return []
		case FirmwareType.VENDOR:
			return [v.value for v in config.vendors]
