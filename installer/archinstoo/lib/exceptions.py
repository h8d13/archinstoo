from subprocess import CalledProcessError
from typing import override


class RequirementError(Exception):
	pass


class DiskError(Exception):
	pass


class UnknownFilesystemFormat(Exception):
	pass


# CalledProcessError subclass so both exec paths (SysCommand and general.run)
# raise one type: 'except SysCallError' and 'except CalledProcessError' each
# catch either path, whichever vocabulary the call site was written for.
class SysCallError(CalledProcessError):
	def __init__(
		self,
		message: str,
		exit_code: int | None = None,
		worker_log: bytes = b'',
		cmd: str | list[str] = '',
		output: bytes | None = None,
		stderr: bytes | None = None,
	) -> None:
		super().__init__(exit_code if exit_code is not None else 1, cmd or message, output, stderr)
		self.message = message
		self.exit_code = exit_code
		self.worker_log = worker_log

	@override
	def __str__(self) -> str:
		# parent's "Command ... returned non-zero exit status" would
		# replace the message every existing f'{err}' log relies on
		return self.message


class HardwareIncompatibilityError(Exception):
	pass


class ServiceException(Exception):
	pass


class DownloadTimeout(Exception):
	# Stub from installer/archinstoo/lib/utils/net.py
	pass
