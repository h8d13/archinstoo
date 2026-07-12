# Some docs in .github/ are symlinks into the repo (index.md -> ../README.md).
# edit_uri builds links from the docs path, so those land on GitHub's symlink
# stub page. Rewrite edit_url to the resolved target for symlinked pages.
import os


def on_pre_page(page, config, files):
	src = page.file.abs_src_path
	if src and os.path.islink(src):
		repo_root = os.path.dirname(config.config_file_path)
		real = os.path.relpath(os.path.realpath(src), repo_root)
		if not real.startswith(".."):
			page.edit_url = (config.repo_url.rstrip("/")
				+ "/blob/master/" + real.replace(os.sep, "/"))
	return page
