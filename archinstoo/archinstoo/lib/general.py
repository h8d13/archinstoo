import contextlib
import json
import os
import re
import shlex
import stat
import subprocess
import sys
import time
from datetime import date, datetime
from enum import Enum
from pathlib import Path
from select import EPOLLHUP, EPOLLIN, epoll
from typing import TYPE_CHECKING, Any, Self, override

from .exceptions import SysCallError
from .output import debug, error, logger
from .utils.env import Os

if TYPE_CHECKING:
	from collections.abc import Iterator
	from types import TracebackType

# https://stackoverflow.com/a/43627833/929999
# expanded strip ANSI/VT100 escapes: CSI (\x1B[...), OSC (\x1B]...BEL/ST), and single Fe escapes.
# order matters: CSI and OSC must precede the Fe branch or \x1B] matches as a 2-char escape.
_VT100_ESCAPE_REGEX = r'\x1B(?:\[[0-?]*[ -/]*[@-~]|\][^\x07\x1B]*(?:\x07|\x1B\\)|[@-Z\\^_])'
_VT100_ESCAPE_REGEX_BYTES = _VT100_ESCAPE_REGEX.encode()


def clear_vt100_escape_codes(data: bytes) -> bytes:
	return re.sub(_VT100_ESCAPE_REGEX_BYTES, b'', data)


def jsonify(obj: object, safe: bool = True) -> Any:  # noqa: ANN401 - dynamic JSON serializer
	# Converts objects into json.dumps() compatible nested dictionaries.
	# Setting safe to True skips dictionary keys starting with a bang (!)

	compatible_types = str, int, float, bool
	if isinstance(obj, dict):
		return {
			key: jsonify(value, safe)
			for key, value in obj.items()
			if isinstance(key, compatible_types) and not (isinstance(key, str) and key.startswith('!') and safe)
		}
	if isinstance(obj, Enum):
		return obj.value
	if hasattr(obj, 'json'):
		# json() is a friendly name for json-helper, it should return
		# a dictionary representation of the object so that it can be
		# processed by the json library.
		return jsonify(obj.json(), safe)
	if isinstance(obj, datetime | date):
		return obj.isoformat()
	if isinstance(obj, list | set | tuple):
		return [jsonify(item, safe) for item in obj]
	if isinstance(obj, Path):
		return str(obj)
	if hasattr(obj, '__dict__'):
		return vars(obj)

	return obj


class JSON(json.JSONEncoder, json.JSONDecoder):
	# we do not store any enc pw or auth data
	@override
	def encode(self, o: Any) -> str:
		return super().encode(jsonify(o))


class SysCommandWorker:
	def __init__(
		self,
		cmd: str | list[str],
		peek_output: bool | None = False,
		environment_vars: dict[str, str] | None = None,
		working_directory: str = './',
		remove_vt100_escape_codes_from_lines: bool = True,
		silent: bool = False,
	):
		if isinstance(cmd, str):
			cmd = shlex.split(cmd)

		if cmd and not cmd[0].startswith(('/', './')):  # Path() does not work well
			cmd[0] = Os.locate_binary(cmd[0])

		self.cmd = cmd
		self.peek_output = peek_output
		# silent: still capture peeked output to cmd_output.txt, but don't echo it to the terminal
		self.silent = silent
		# define the standard locale for command outputs. For now the C ascii one. Can be overridden
		self.environment_vars = {'LC_ALL': 'C'}
		if environment_vars:
			self.environment_vars.update(environment_vars)

		self.working_directory = working_directory

		self.exit_code: int | None = None
		self._trace_log = b''
		self._trace_log_pos = 0
		self.poll_object = epoll()
		self.child_fd: int | None = None
		self.started = False
		self.ended = False
		self.remove_vt100_escape_codes_from_lines: bool = remove_vt100_escape_codes_from_lines

	def __contains__(self, key: bytes) -> bool:
		# Contains will also move the current buffert position forward.
		# This is to avoid re-checking the same data when looking for output.
		index = self._trace_log.find(key, self._trace_log_pos)
		if index >= 0:
			self._trace_log_pos += index + len(key)
			return True

		return False

	def __iter__(self, *args: str, **kwargs: dict[str, Any]) -> Iterator[bytes]:
		last_line = self._trace_log.rfind(b'\n')
		lines = filter(None, self._trace_log[self._trace_log_pos : last_line].splitlines())
		for line in lines:
			if self.remove_vt100_escape_codes_from_lines:
				line = clear_vt100_escape_codes(line)

			yield line + b'\n'

		self._trace_log_pos = last_line

	@override
	def __repr__(self) -> str:
		self.make_sure_we_are_executing()
		return str(self._trace_log)

	@override
	def __str__(self) -> str:
		try:
			return self._trace_log.decode('utf-8')
		except UnicodeDecodeError:
			return str(self._trace_log)

	def __enter__(self) -> Self:
		return self

	def __exit__(self, exc_type: type[BaseException] | None, exc_value: BaseException | None, traceback: TracebackType | None) -> None:
		# b''.join(sys_command('sync')) # No need to, since the underlying fs() object will call sync.
		# TODO: https://stackoverflow.com/questions/28157929/how-to-safely-handle-an-exception-inside-a-context-manager

		if self.child_fd:
			with contextlib.suppress(Exception):
				os.close(self.child_fd)

		if self.peek_output:
			if not self.silent:
				# To make sure any peaked output didn't leave us hanging
				# on the same line we were on.
				sys.stdout.write('\n')
				sys.stdout.flush()
			_cmd_output_flush()

		if exc_type is not None:
			debug(str(exc_value))

		if self.exit_code != 0:
			cleaned_log = clear_vt100_escape_codes(self._trace_log)
			raise SysCallError(
				f'{self.cmd} exited with abnormal exit code [{self.exit_code}]: {cleaned_log.decode("utf-8", errors="ignore")[-500:]}',
				self.exit_code,
				worker_log=cleaned_log,
			)

	def is_alive(self) -> bool:
		self.poll()

		return bool(self.started and not self.ended)

	def write(self, data: bytes, line_ending: bool = True) -> int:
		# TODO: Maybe we can support str as well and encode it
		self.make_sure_we_are_executing()

		if self.child_fd:
			return os.write(self.child_fd, data + (b'\n' if line_ending else b''))

		return 0

	def make_sure_we_are_executing(self) -> bool:
		if not self.started:
			return self.execute()
		return True

	def seek(self, pos: int) -> None:
		self.make_sure_we_are_executing()
		# Safety check to ensure 0 < pos < len(tracelog)
		self._trace_log_pos = min(max(0, pos), len(self._trace_log))

	def peak(self, output: str | bytes) -> bool:
		if self.peek_output:
			if isinstance(output, bytes):
				try:
					output = output.decode('UTF-8')
				except UnicodeDecodeError:
					return False

			_cmd_output(output)

			if not self.silent:
				sys.stdout.write(output)
				sys.stdout.flush()

		return True

	def poll(self) -> None:
		self.make_sure_we_are_executing()

		if self.child_fd:
			got_output = False
			for _fileno, _event in self.poll_object.poll(0.1):
				try:
					output = os.read(self.child_fd, 8192)
					got_output = True
					self.peak(output)
					self._trace_log += output
				except OSError:
					# pty closed: command done and no process holds the slave
					self.ended = True
					break

			if self.ended:
				self._reap()
			elif not got_output and self.pid is not None:
				# pty can stay open on a leaked daemon (gnupg post_install spawns
				# dirmngr); reap the child by pid so a held slave can't hang us
				try:
					reaped, wait_status = os.waitpid(self.pid, os.WNOHANG)
				except ChildProcessError:
					self.ended = True
					self.exit_code = 1
					return

				if reaped:
					self.ended = True
					self.exit_code = os.waitstatus_to_exitcode(wait_status)

	def _reap(self) -> None:
		# prefer the pid; fall back to the pty fd if it was already reaped
		if self.pid is not None:
			try:
				wait_status = os.waitpid(self.pid, 0)[1]
				self.exit_code = os.waitstatus_to_exitcode(wait_status)
				return
			except ChildProcessError:
				pass

		if self.child_fd is not None:
			try:
				wait_status = os.waitpid(self.child_fd, 0)[1]
				self.exit_code = os.waitstatus_to_exitcode(wait_status)
				return
			except ChildProcessError:
				pass

		self.exit_code = 1

	def execute(self) -> bool:
		import pty

		if (old_dir := str(Path.cwd())) != self.working_directory:
			os.chdir(str(self.working_directory))

		# Note: If for any reason, we get a Python exception between here
		#   and until os.close(), the traceback will get locked inside
		#   stdout of the child_fd object. `os.read(self.child_fd, 8192)` is the
		#   only way to get the traceback without losing it.

		self.pid, self.child_fd = pty.fork()

		# https://stackoverflow.com/questions/4022600/python-pty-fork-how-does-it-work
		if not self.pid:
			_cmd_history(self.cmd)

			try:
				os.execve(self.cmd[0], list(self.cmd), {**os.environ, **self.environment_vars})  # noqa: S606 - SysCommand intentionally runs without a shell
			except FileNotFoundError:
				error(f'{self.cmd[0]} does not exist.')
				self.exit_code = 1
				return False
		else:
			# Only parent process moves back to the original working directory
			os.chdir(old_dir)

		self.started = True
		self.poll_object.register(self.child_fd, EPOLLIN | EPOLLHUP)

		return True

	def decode(self, encoding: str = 'UTF-8') -> str:
		return self._trace_log.decode(encoding)


class SysCommand:
	def __init__(
		self,
		cmd: str | list[str],
		peek_output: bool | None = False,
		environment_vars: dict[str, str] | None = None,
		working_directory: str = './',
		remove_vt100_escape_codes_from_lines: bool = True,
		silent: bool = False,
	):
		self.cmd = cmd
		self.peek_output = peek_output
		self.silent = silent
		self.environment_vars = environment_vars
		self.working_directory = working_directory
		self.remove_vt100_escape_codes_from_lines = remove_vt100_escape_codes_from_lines

		self.session: SysCommandWorker | None = None
		self.create_session()

	def __enter__(self) -> SysCommandWorker | None:
		return self.session

	def __exit__(self, exc_type: type[BaseException] | None, exc_value: BaseException | None, traceback: TracebackType | None) -> None:
		# b''.join(sys_command('sync')) # No need to, since the underlying fs() object will call sync.
		# TODO: https://stackoverflow.com/questions/28157929/how-to-safely-handle-an-exception-inside-a-context-manager

		if exc_type is not None:
			error(str(exc_value))

	def __iter__(self, *args: list[Any], **kwargs: dict[str, Any]) -> Iterator[bytes]:
		if self.session:
			yield from self.session

	def __getitem__(self, key: slice) -> bytes:
		if not self.session:
			raise KeyError('SysCommand() does not have an active session.')
		if type(key) is slice:
			start = key.start or 0
			end = key.stop or len(self.session._trace_log)

			return self.session._trace_log[start:end]
		raise ValueError("SysCommand() doesn't have key & value pairs, only slices, SysCommand('ls')[:10] as an example.")

	@override
	def __repr__(self, *args: list[Any], **kwargs: dict[str, Any]) -> str:
		return self.decode('UTF-8', errors='backslashreplace') or ''

	def create_session(self) -> bool:
		# Initiates a :ref:`SysCommandWorker` session in this class ``.session``.
		# It then proceeds to poll the process until it ends, after which it also
		# clears any printed output if ``.peek_output=True``.
		if self.session:
			return True

		with SysCommandWorker(
			self.cmd,
			peek_output=self.peek_output,
			environment_vars=self.environment_vars,
			remove_vt100_escape_codes_from_lines=self.remove_vt100_escape_codes_from_lines,
			working_directory=self.working_directory,
			silent=self.silent,
		) as session:
			self.session = session

			while not self.session.ended:
				self.session.poll()

		if self.peek_output and not self.silent:
			sys.stdout.write('\n')
			sys.stdout.flush()

		return True

	def decode(self, encoding: str = 'utf-8', errors: str = 'backslashreplace', strip: bool = True) -> str:
		if not self.session:
			raise ValueError('No session available to decode')

		val = self.session._trace_log.decode(encoding, errors=errors)

		if strip:
			return val.strip()
		return val

	def output(self, remove_cr: bool = True) -> bytes:
		if not self.session:
			raise ValueError('No session available')

		if remove_cr:
			return self.session._trace_log.replace(b'\r\n', b'\n')

		return self.session._trace_log

	@property
	def exit_code(self) -> int | None:
		if self.session:
			return self.session.exit_code
		return None


def _append_log(file: str, content: str) -> None:
	path = logger.directory / file

	change_perm = not path.exists()

	try:
		with path.open('a') as f:
			f.write(content)

		if change_perm:
			path.chmod(stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP)
	except PermissionError, FileNotFoundError:
		# If the file does not exist, ignore the error
		pass


def _cmd_history(cmd: list[str]) -> None:
	content = f'{time.time()} {cmd}\n'
	_append_log('cmd_history.txt', content)


class _CmdOutputLog:
	# the pty delivers redraw output in fragments, so blank-line capping and partial-line
	# assembly carry state across writes; flush() drains the trailing partial at command end.
	def __init__(self) -> None:
		self._buffer = ''
		self._blank_run = 0

	def write(self, output: str) -> None:
		cleaned = re.sub(_VT100_ESCAPE_REGEX, '', output)
		cleaned = cleaned.replace('\r\n', '\n')  # the pty's ONLCR delivers every \n as \r\n
		cleaned = re.sub(r'[^\n]*\r', '', cleaned)  # collapse bare-\r progress redraws to the final frame
		cleaned = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', cleaned)  # leftover C0 controls (SI/SO/BEL/...), keep \t \n

		self._buffer += cleaned
		*lines, self._buffer = self._buffer.split('\n')  # keep the trailing partial line buffered

		out = []
		for line in lines:
			if line.strip():
				self._blank_run = 0
				out.append(line)
			else:
				# in-place redraws leave runs of blank lines; keep at most one
				self._blank_run += 1
				if self._blank_run <= 1:
					out.append('')

		if out:
			_append_log('cmd_output.txt', '\n'.join(out) + '\n')

	def flush(self) -> None:
		if self._buffer:
			_append_log('cmd_output.txt', self._buffer + '\n')
		self._buffer = ''
		self._blank_run = 0


_cmd_output_log = _CmdOutputLog()


def _cmd_output(output: str) -> None:
	# clean here, not in peak(): stdout still wants the raw colored stream
	_cmd_output_log.write(output)


def _cmd_output_flush() -> None:
	_cmd_output_log.flush()


def run(
	cmd: list[str],
	input_data: bytes | None = None,
) -> subprocess.CompletedProcess[bytes]:
	_cmd_history(cmd)

	return subprocess.run(  # noqa: S603 - cmd is project-controlled list, not user input
		cmd,
		input=input_data,
		capture_output=True,
		check=True,
	)
