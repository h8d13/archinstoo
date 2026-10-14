# Flag string literals spelling 3+ text lines with \n escapes: a dedent()'ed
# triple-quoted block reads better. Blank lines don't count, so '\n\n'
# spacers pass. Opt out with a trailing '# dedent: skip'.
import ast
import sys
from pathlib import Path

MIN_LINES = 3
SKIP = '# dedent: skip'


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


def main(paths: list[str]) -> int:
	hits = set()
	for path in paths:
		src = Path(path).read_text()
		lines = src.splitlines()
		nodes = list(ast.walk(ast.parse(src, path)))
		# f-string parts have no quotes of their own, judge the whole
		parts = {id(v) for n in nodes if isinstance(n, ast.JoinedStr) for v in n.values}
		for node in nodes:
			if id(node) in parts or not isinstance(node, ast.expr):
				continue
			if not is_inline_block(src, node):
				continue
			if SKIP in lines[(node.end_lineno or node.lineno) - 1]:
				continue
			hits.add((path, node.lineno, lines[node.lineno - 1].strip()))
	for path, lineno, line in sorted(hits):
		print(f'{path}:{lineno}: {line}')
	return 1 if hits else 0


if __name__ == '__main__':
	sys.exit(main(sys.argv[1:]))
