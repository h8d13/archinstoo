# Regenerate schema.toml from the installer's own package definitions.
#
# Usage: python -m archinstoo --script schema

from archinstoo.lib.schema import SCHEMA_PATH
from archinstoo.lib.schema_gen import write

write()
print(f'wrote {SCHEMA_PATH}')
