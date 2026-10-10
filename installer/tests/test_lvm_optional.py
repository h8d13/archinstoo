# lvm2 is an optdepend: an H2T host without it must still wipe a plain disk.
# wipe_dev used to call pvs unconditionally, and a missing binary raises
# RequirementError, which the SysCallError guards there never caught.

from typing import TYPE_CHECKING

from archinstoo.lib.disk import device_handler
from archinstoo.lib.disk.device_handler import DeviceHandler

if TYPE_CHECKING:
	import pytest


def test_lvm_teardown_skipped_without_pvs(monkeypatch: pytest.MonkeyPatch) -> None:
	monkeypatch.setattr(device_handler, 'which', lambda _: None)

	def fail(*_: object, **__: object) -> None:
		raise AssertionError('SysCommand ran without lvm2')

	monkeypatch.setattr(device_handler, 'SysCommand', fail)

	# self/device untouched once pvs is known missing
	DeviceHandler.lvm_deactivate_vgs_on_device(None, None)  # type: ignore[arg-type]
