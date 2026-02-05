# Sphinx configuration for man page generation only
project = 'archinstoo'
author = 'h8d13'

master_doc = 'index'
exclude_patterns = ['_build']

# Man page output
# (source start file, name, description, authors, manual section)
man_pages = [('index', 'archinstoo', 'Arch Linux guided installer', [author], 1)]
