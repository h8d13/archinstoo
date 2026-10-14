# Some docs in .github/ are symlinks into the repo (index.md -> ../README.md).
# edit_uri builds links from the docs path, so those land on GitHub's symlink
# stub page. Rewrite edit_url to the resolved target for symlinked pages.
#
# The same docs also render on GitHub, so cross-doc links are absolute repo
# URLs. On the site, rewrite those pointing at a built doc to relative links.
import os
import posixpath
import re
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
	from mkdocs.config.defaults import MkDocsConfig
	from mkdocs.structure.files import Files
	from mkdocs.structure.pages import Page

# repo-relative real path -> doc src_uri, filled in on_files
_docs: dict[str, str] = {}


def _repo_rel(abs_path: str, repo_root: Path) -> str | None:
	# relpath, not relative_to: '..' is the out-of-tree signal
	real = os.path.relpath(Path(abs_path).resolve(), repo_root)
	if real.startswith('..'):
		return None
	return real.replace(os.sep, '/')


def on_files(files: Files, config: MkDocsConfig) -> Files:
	repo_root = Path(config.config_file_path).parent
	_docs.clear()
	for f in files.documentation_pages():
		if f.abs_src_path and (real := _repo_rel(f.abs_src_path, repo_root)):
			_docs[real] = f.src_uri
	return files


def on_pre_page(page: Page, config: MkDocsConfig, files: Files) -> Page:
	src = page.file.abs_src_path
	if src and Path(src).is_symlink():
		repo_root = Path(config.config_file_path).parent
		if real := _repo_rel(src, repo_root):
			page.edit_url = config.repo_url.rstrip('/') + '/blob/master/' + real
	return page


def _doc_for(path: str) -> str | None:
	path = path.strip('/')
	# repo root and dirs render their README on GitHub
	for cand in (path, posixpath.join(path, 'README.md')):
		if cand in _docs:
			return _docs[cand]
	return None


def on_page_markdown(markdown: str, page: Page, config: MkDocsConfig, files: Files) -> str:
	# ](repo_url[/blob|tree/master/path][?query][#anchor])
	link = re.compile(r'\]\(' + re.escape(config.repo_url.rstrip('/')) + r'(?:/(?:blob|tree)/master(/[^)?#\s]*))?(?:\?[^)#\s]*)?(#[^)\s]*)?\)')
	page_dir = posixpath.dirname(page.file.src_uri) or '.'

	def repl(m: re.Match[str]) -> str:
		path, anchor = m.group(1), m.group(2) or ''
		# bare repo URL means the repo itself, not its README
		if not (path or anchor):
			return m.group(0)
		doc = _doc_for(path or '')
		if doc is None:
			return m.group(0)
		return '](' + posixpath.relpath(doc, page_dir) + anchor + ')'

	return link.sub(repl, markdown)
