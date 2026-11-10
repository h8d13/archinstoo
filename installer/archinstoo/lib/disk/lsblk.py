import json
from dataclasses import dataclass
from pathlib import Path
from subprocess import CalledProcessError

from archinstoo.lib.command import run
from archinstoo.lib.exceptions import DiskError, SysCallError
from archinstoo.lib.models.device import LsblkInfo
from archinstoo.lib.output import debug, warn


@dataclass
class LsblkOutput:
	blockdevices: list[LsblkInfo]

	@classmethod
	def from_json(cls, data: str) -> LsblkOutput:
		parsed = json.loads(data)
		devices = [
			LsblkInfo.from_dict(d) for d in parsed.get('blockdevices', [])
		]
		return cls(blockdevices=devices)

	def to_json(self) -> str:
		return json.dumps(
			{'blockdevices': [d.to_dict() for d in self.blockdevices]},
			indent=4,
		)


def _fetch_lsblk_info(
	dev_path: Path | str | None = None,
	reverse: bool = False,
	full_dev_path: bool = False,
) -> LsblkOutput:
	cmd = ['lsblk', '--json', '--bytes', '--output', ','.join(LsblkInfo.fields())]

	if reverse:
		cmd.append('--inverse')

	if full_dev_path:
		cmd.append('--paths')

	if dev_path:
		cmd.append(str(dev_path))

	try:
		result = run(cmd)
	except CalledProcessError as err:
		# Get the output minus the message/info from lsblk if it returns
		# a non-zero exit code.
		if stdout := err.stdout:
			debug(f'Error calling lsblk: {stdout.decode().rstrip()}')

		if dev_path:
			raise DiskError(
				f'Failed to read disk "{dev_path}" with lsblk'
			) from err

		raise

	return LsblkOutput.from_json(result.stdout.decode())


def get_lsblk_info(
	dev_path: Path | str,
	reverse: bool = False,
	full_dev_path: bool = False,
) -> LsblkInfo:
	infos = _fetch_lsblk_info(
		dev_path, reverse=reverse, full_dev_path=full_dev_path
	)

	if infos.blockdevices:
		return infos.blockdevices[0]

	raise DiskError(f'lsblk failed to retrieve information for "{dev_path}"')


def get_all_lsblk_info() -> list[LsblkInfo]:
	return _fetch_lsblk_info().blockdevices


def get_lsblk_output() -> LsblkOutput:
	return _fetch_lsblk_info()


def find_lsblk_info(
	dev_path: Path | str,
	info_list: list[LsblkInfo],
) -> LsblkInfo | None:
	if isinstance(dev_path, str):
		dev_path = Path(dev_path)

	for lsblk_info in info_list:
		if lsblk_info.path == dev_path:
			return lsblk_info

	return None


def get_lsblk_by_mountpoint(
	mountpoint: Path, as_prefix: bool = False
) -> list[LsblkInfo]:
	def _check(infos: list[LsblkInfo]) -> list[LsblkInfo]:
		devices = []
		for entry in infos:
			if as_prefix:
				matches = [
					m
					for m in entry.mountpoints
					if str(m).startswith(str(mountpoint))
				]
				if matches:
					devices += [entry]
			elif mountpoint in entry.mountpoints:
				devices += [entry]

			if (
				len(entry.children) > 0
				and len(match := _check(entry.children)) > 0
			):
				devices += match

		return devices

	all_info = get_all_lsblk_info()
	return _check(all_info)


def disk_layouts() -> str:
	try:
		lsblk_output = get_lsblk_output()
	except SysCallError as err:
		warn(f'Could not return disk layouts: {err}')
		return ''

	return lsblk_output.to_json()


def get_parent_device_path(dev_path: Path) -> Path:
	lsblk = get_lsblk_info(dev_path)
	return Path(f'/dev/{lsblk.pkname}')
