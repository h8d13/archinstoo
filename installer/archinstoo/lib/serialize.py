import json
from datetime import date, datetime
from enum import Enum
from pathlib import Path
from typing import Any, override

from .output import HasJson


def jsonify(obj: object, safe: bool = True) -> Any:  # noqa: ANN401 - dynamic JSON serializer
	# Converts objects into json.dumps() compatible nested dictionaries.
	# Setting safe to True skips dictionary keys starting with a bang (!)
	# Unset values (None / '') are omitted: loaders presence-check keys and
	# fall back to defaults, and _cleanup_config strips None on load anyway.

	compatible_types = str, int, float, bool
	if isinstance(obj, dict):
		return {
			key: jsonify(value, safe)
			for key, value in obj.items()
			if isinstance(key, compatible_types)
			and not (isinstance(key, str) and key.startswith('!') and safe)
			and value is not None
			and value != ''  # noqa: PLC1901 - value is Any, truthiness would also drop False/0
		}
	if isinstance(obj, Enum):
		return obj.value
	if isinstance(obj, HasJson):
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
