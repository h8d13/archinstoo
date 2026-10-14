# Flag string literals spelling 3+ text lines with \n escapes: a dedent()'ed
# triple-quoted block reads better. Blank lines don't count, so '\n\n'
# spacers pass. Takes files (pre-commit passes staged ones) or directories,
# scanned whole for a manual full run.
import ast
import sys
from pathlib import Path

MIN_LINES = 3
# synced from upstream, ruff skips it too
EXCLUDE = {'grimoire.py'}


def _text(node: ast.AST) -> str | None:
	if isinstance(node, ast.Constant) and isinstance(node.value, str | bytes):
		v = node.value
		return v.decode('latin-1') if isinstance(v, bytes) else v
	if isinstance(node, ast.JoinedStr):
		# a placeholder fills its line, so f'{a}\n{b}\n{c}' is 3 lines
		return ''.join(_text(v) or 'x' for v in node.values)
	return None


def is_inline_block(src: str, node: ast.expr) -> bool:
	text = _text(node)
	seg = ast.get_source_segment(src, node) or ''
	# triple quotes hold real newlines, that's already the fix
	if text is None or '"""' in seg or "'''" in seg:
		return False
	return sum(1 for line in text.split('\n') if line.strip()) >= MIN_LINES


def _sources(args: list[str]) -> list[Path]:
	paths = [p for arg in args for p in (Path(arg).rglob('*.py') if Path(arg).is_dir() else [Path(arg)])]
	return [p for p in paths if p.name not in EXCLUDE]


def main(args: list[str]) -> int:
	hits = set()
	for path in _sources(args):
		src = path.read_text()
		lines = src.splitlines()
		nodes = list(ast.walk(ast.parse(src, path)))
		# f-string parts have no quotes of their own, judge the whole
		parts = {id(v) for n in nodes if isinstance(n, ast.JoinedStr) for v in n.values}
		for node in nodes:
			if id(node) in parts or not isinstance(node, ast.expr):
				continue
			if is_inline_block(src, node):
				hits.add((str(path), node.lineno, lines[node.lineno - 1].strip()))
	for path, lineno, line in sorted(hits):
		print(f'{path}:{lineno}: {line}')
	return 1 if hits else 0


if __name__ == '__main__':
	sys.exit(main(sys.argv[1:]))
