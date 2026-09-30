# The passphrase handed to systemd-cryptenroll lands on the target's disk as a
# keyfile; it must be gone after enrollment, including when enrollment raises.

from typing import TYPE_CHECKING

import pytest

from archinstoo.lib.disk.cryptenroll import _bootstrap_key

if TYPE_CHECKING:
	from pathlib import Path


def test_bootstrap_key_written_then_removed(tmp_path: Path) -> None:
	with _bootstrap_key(tmp_path, '.fido2-bootstrap.key', 'hunter2') as key:
		assert key.read_text() == 'hunter2'
		assert key.stat().st_mode & 0o777 == 0o400
	assert not key.exists()


def test_bootstrap_key_removed_on_error(tmp_path: Path) -> None:
	with pytest.raises(RuntimeError), _bootstrap_key(tmp_path, '.fido2-bootstrap.key', 'hunter2') as key:
		raise RuntimeError
	assert not key.exists()
