# Some docs in .github/ are symlinks into the repo (index.md -> ../README.md).
# edit_uri builds links from the docs path, so those land on GitHub's symlink
# stub page. Rewrite edit_url to the resolved target for symlinked pages.
import os
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
	from mkdocs.config.defaults import MkDocsConfig
	from mkdocs.structure.files import Files
	from mkdocs.structure.pages import Page


def on_pre_page(page: Page, config: MkDocsConfig, files: Files) -> Page:
	src = page.file.abs_src_path
	if src and Path(src).is_symlink():
		repo_root = Path(config.config_file_path).parent
		# relpath, not relative_to: '..' is the out-of-tree signal below
		real = os.path.relpath(Path(src).resolve(), repo_root)
		if not real.startswith('..'):
			page.edit_url = config.repo_url.rstrip('/') + '/blob/master/' + real.replace(os.sep, '/')
	return page
