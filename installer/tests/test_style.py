# archinstoo documents with short inline `# why` comments rather than
# docstrings. No linter has a rule for the absence of one: all 42 of ruff's
# docstring rules require or format them, and PYI021 is stub-files only. So the
# convention is checked here instead of drifting on review attention alone.

import ast
from pathlib import Path

_TESTS = Path(__file__).parent
_PACKAGE = _TESTS.parent / 'archinstoo'

# the package banner, and a standalone tool copied to the target as
# /usr/local/bin/grimoire, whose header is read by users rather than developers
_ALLOWED = {'__init__.py', 'grimoire.py'}


def test_comments_not_docstrings() -> None:
	found: list[str] = []

	for root in (_PACKAGE, _TESTS):
		for path in sorted(root.rglob('*.py')):
			if path.name in _ALLOWED:
				continue

			tree = ast.parse(path.read_text())
			scopes = (n for n in ast.walk(tree) if isinstance(n, ast.AsyncFunctionDef | ast.ClassDef | ast.FunctionDef))
			found.extend(f'{path.relative_to(root.parent)}:{node.body[0].lineno}' for node in (tree, *scopes) if ast.get_docstring(node))

	assert not found, f'use a `# why` comment instead of a docstring: {found}'
