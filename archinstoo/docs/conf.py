# Sphinx configuration for man page generation only
import os
import sys

sys.path.insert(0, os.path.abspath('..'))

project = 'archinstoo'
author = 'h8d13'

master_doc = 'index'
exclude_patterns = ['_build']

extensions = [
	'sphinx.ext.autodoc',
]

# Man page output
# (source start file, name, description, authors, manual section)
man_pages = [('index', 'archinstoo', 'archinstoo Documentation', [author], 1)]
