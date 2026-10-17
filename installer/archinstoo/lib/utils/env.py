import os

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

	@staticmethod
	def del_value(key: str) -> None:
		# no-op when unset
		os.environ.pop(key, None)

	# getters
	@staticmethod
	def has_value(key: str) -> bool:
		return key in os.environ

	# if is missing, set a default. or don't.
	@staticmethod
	def get_value(key: str, default: str | None = None) -> str | None:
		return os.environ.get(key, default)

	# useful for cli tool invocations
	@staticmethod
	def get_bool(key: str, default: bool = False) -> bool:
		# set but empty counts as unset, like shell ${FOO:-default}
		if not (value := _normalize(os.environ.get(key, ''))):
			return default

		return value in _TRUTHY_VALS

	# misc
	# this is not thread safe. inherits from the python process
	# should be used only as such, for the current process envir
	@staticmethod
	def rel_envir() -> None:
		os.reload_environ()
