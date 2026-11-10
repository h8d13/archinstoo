import http.client
import urllib.error
import urllib.request
from typing import TYPE_CHECKING

from archinstoo.lib.hardware import SysInfo
from archinstoo.lib.output import debug
from archinstoo.lib.utils.net import DownloadTimer

if TYPE_CHECKING:
	from archinstoo.lib.models.mirrors import MirrorStatusEntryV3

# the network side of a mirror entry: the model only holds what was measured


def mirror_speed(mirror: MirrorStatusEntryV3, retries: int = 3) -> float:
	# bytes/s, measured once per entry and kept on it
	if mirror.speed is None:
		mirror.speed = _measure_speed(mirror, max(retries, 1))
	return mirror.speed


def _measure_speed(mirror: MirrorStatusEntryV3, retries: int) -> float:
	speed: float | None = None
	test_db = f'{mirror.url}core/os/{SysInfo.arch()}/core.db'

	retry = 0
	while retry < retries and speed is None:
		debug(
			'Checking download speed of '
			f'{mirror.hostname}[{mirror.score}] by '
			f'fetching: {test_db}'
		)

		req = urllib.request.Request(url=test_db)  # noqa: S310

		try:
			# timer first: arms SIGALRM before urlopen so
			# the timeout bounds the connect phase too, not
			# just read(). Else a multi-homed unreachable
			# mirror walks every dead address at 5s each
			# (Errno 101 / pre-403 stalls) before skipping.
			with (
				DownloadTimer(timeout=5) as timer,
				urllib.request.urlopen(  # noqa: S310
					req, None, 5
				) as handle,
			):
				size = len(handle.read())

			if timer.time is None:
				raise RuntimeError(
					'DownloadTimer exited without recording time'
				)
			speed = size / timer.time
			mib = int(speed / 1024 / 1024 * 100) / 100
			debug(f'    speed: {speed} ({mib}MiB/s)')
		# Do not retry error
		except urllib.error.URLError as error:
			debug(f'    speed: <undetermined> ({error}), skip')
			speed = 0
		# Do retry error
		except (
			http.client.IncompleteRead,
			ConnectionResetError,
		) as error:
			debug(f'    speed: <undetermined> ({error}), retry')
		# Catch all
		except Exception as error:
			debug(f'    speed: <undetermined> ({error}), skip')
			speed = 0

		retry += 1

	return speed or 0
