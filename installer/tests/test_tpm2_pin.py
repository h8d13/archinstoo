# TPM2 keyslot optionally bound to a PIN: --tpm2-with-pin=yes at enrollment, the PIN
# handed over via NEWPIN so it never lands on argv. https://github.com/archlinux/archinstall/issues/1584

from pathlib import Path
from types import SimpleNamespace
from typing import Any

from archinstoo.lib.installer import Installer
from archinstoo.lib.models.device import (
	DiskEncryption,
	EncryptionType,
	ModificationStatus,
	PartitionModification,
	PartitionType,
	SectorSize,
	Size,
	Unit,
)
from archinstoo.lib.models.users import Password

SECTOR = SectorSize.default()


def _root() -> PartitionModification:
	return PartitionModification(
		status=ModificationStatus.CREATE,
		type=PartitionType.PRIMARY,
		start=Size(1, Unit.MiB, SECTOR),
		length=Size(1, Unit.GiB, SECTOR),
		mountpoint=Path('/'),
		dev_path=Path('/dev/vda2'),
	)


def _enroll(tmp_path: Path, pin: Password | None) -> list[tuple[list[str], dict[str, str] | None]]:
	calls: list[tuple[list[str], dict[str, str] | None]] = []
	inst = Installer.__new__(Installer)
	inst.target = tmp_path
	inst._disk_encryption = DiskEncryption(
		EncryptionType.LUKS,
		encryption_password=Password(plaintext='hunter2'),
		partitions=[_root()],
		tpm2_unlock=True,
		tpm2_pin=pin,
	)

	def fake_chroot(cmd: list[str], run_as: str | None = None, peek_output: bool = False, env: dict[str, str] | None = None) -> None:
		calls.append((cmd, env))

	inst.arch_chroot = fake_chroot  # type: ignore[method-assign, assignment]
	inst.enroll_tpm2()
	return calls


def test_enroll_with_pin(tmp_path: Path) -> None:
	((cmd, env),) = _enroll(tmp_path, Password(plaintext='1234'))
	assert '--tpm2-with-pin=yes' in cmd
	assert env == {'NEWPIN': '1234'}
	assert '1234' not in ' '.join(cmd)


def test_enroll_without_pin(tmp_path: Path) -> None:
	((cmd, env),) = _enroll(tmp_path, None)
	assert '--tpm2-with-pin=yes' not in cmd
	assert env is None


def test_bootstrap_key_removed_after_enroll(tmp_path: Path) -> None:
	_enroll(tmp_path, Password(plaintext='1234'))
	assert not (tmp_path / 'etc/cryptsetup-keys.d/.tpm2-bootstrap.key').exists()


def test_parse_pin_from_config() -> None:
	root = _root()
	disk_config = SimpleNamespace(device_modifications=[SimpleNamespace(partitions=[root])], lvm_config=None)
	arg: dict[str, Any] = {
		'encryption_type': 'luks',
		'encryption_password': 'hunter2',
		'partitions': [root.obj_id],
		'tpm2_unlock': True,
		'tpm2_pin': '1234',
	}
	enc = DiskEncryption.parse_arg(arg, disk_config)  # type: ignore[arg-type]
	assert enc.tpm2_pin is not None
	assert enc.tpm2_pin.plaintext == '1234'
