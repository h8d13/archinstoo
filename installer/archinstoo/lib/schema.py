# schema.jsonc: where it lives and how to read it.
#
# The count/size scripts import SCHEMA from here; nvchecker/NVGEN loads this
# module BY PATH to reach the same file and parser without the archinstoo
# runtime. Keep it stdlib-only and free of intra-package imports or that load
# breaks (tests/test_schema_drift.py pins it).

import json
import re
from pathlib import Path
from typing import Any

SCHEMA_PATH = Path(__file__).parent.parent / 'schema.jsonc'

# `// comment` on its own line, or a trailing one that follows a comma. anything
# else (a comment after `]` with no comma) stays in place and surfaces as a
# JSONDecodeError rather than silently eating a line
_COMMENT_RE = re.compile(r'(?m)^\s*//.*$|(?<=,)\s*//.*$')


def load(path: Path = SCHEMA_PATH) -> dict[str, Any]:
	# strip // comments, then parse as json
	result: dict[str, Any] = json.loads(_COMMENT_RE.sub('', path.read_text()))
	return result


SCHEMA = load()
