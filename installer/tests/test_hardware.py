# DMI strings come straight from firmware, encoding not guaranteed
from typing import TYPE_CHECKING

from archinstoo.lib import hardware

if TYPE_CHECKING:
	from pathlib import Path

	import pytest


def test_dmi_survives_non_utf8(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
	(tmp_path / 'product_name').write_bytes(b'X\xfbBook 15\n')
	monkeypatch.setattr(hardware, '_DMI_ID', tmp_path)

	assert hardware._read_dmi('product_name') == 'X�Book 15'
