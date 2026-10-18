import os
from pathlib import Path
from typing import overload

# consts
_TRUTHY_VALS = frozenset({'y', 'yes', '1', 'true', 't', 'on'})
# anything else will be considered false...


# helpers
def _normalize(value: str) -> str:
	return value.strip().lower()


class Env:
	# setters
	@staticmethod
	def put_value(key: str, value: str) -> None:
		os.environ[key] = value

	# getters
	@staticmethod
	def has_value(key: str) -> bool:
		return key in os.environ

	# if is missing, set a default. or don't.
	# set but empty counts as unset, like shell ${FOO:-default}
	@overload
	@staticmethod
	def get_value(key: str) -> str | None: ...

	@overload
	@staticmethod
	def get_value(key: str, default: str) -> str: ...

	@staticmethod
	def get_value(key: str, default: str | None = None) -> str | None:
		return os.environ.get(key) or default

	# useful for cli tool invocations
	@staticmethod
	def get_bool(key: str, default: bool = False) -> bool:
		# set but empty counts as unset, like shell ${FOO:-default}
		if not (value := _normalize(os.environ.get(key, ''))):
			return default

		return value in _TRUTHY_VALS

	# ~ expands, a relative path is taken from base (when given)
	@staticmethod
	def get_path(key: str, base: Path | None = None) -> Path | None:
		if not (value := os.environ.get(key)):
			return None

		path = Path(value).expanduser()
		return base / path if base else path

	# copy of the current envir, extras override. for child processes
	@staticmethod
	def get_envir(extra: dict[str, str] | None = None) -> dict[str, str]:
		return os.environ | (extra or {})
