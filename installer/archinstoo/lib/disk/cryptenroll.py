import os
import subprocess
from contextlib import contextmanager
from subprocess import CalledProcessError
from typing import TYPE_CHECKING

from archinstoo.lib.disk.luks import KEYFILE_DIR
from archinstoo.lib.models.device import DiskEncryption, EncryptionType
from archinstoo.lib.output import info, warn

if TYPE_CHECKING:
	from collections.abc import Iterator
	from pathlib import Path

# systemd-cryptenroll adds a FIDO2 keyslot next to the passphrase one, which
# stays as the fallback. It needs the existing passphrase to unlock the slot it
# extends, handed over as a transient keyfile under the standard LUKS
# keyfile dir (same convention as the root auto-unlock keyfile).


@contextmanager
def _bootstrap_key(target: Path, name: str, passphrase: str) -> Iterator[Path]:
	key = target / KEYFILE_DIR.relative_to('/') / name
	key.parent.mkdir(parents=True, exist_ok=True)
	try:
		key.write_bytes(passphrase.encode())
		key.chmod(0o400)
		yield key
	finally:
		key.unlink(missing_ok=True)


def enroll_fido2(target: Path, enc: DiskEncryption) -> None:
	if not (token := enc.fido2_device) or enc.encryption_type == EncryptionType.NO_ENCRYPTION:
		return
	if not (password := enc.encryption_password):
		warn('FIDO2 enrollment skipped: no encryption password available')
		return
	if not (devices := enc.encrypted_dev_paths()):
		warn('FIDO2 enrollment skipped: no encrypted devices in this layout')
		return

	with _bootstrap_key(target, '.fido2-bootstrap.key', password.plaintext) as key:
		# inherited by cryptenroll below: keep PIN/touch prompts plain text
		os.environ['SYSTEMD_EMOJI'] = '0'

		info(f'FIDO2 token: {token.path} ({token.manufacturer} {token.product})')
		# Touch/PIN prompts are easy to miss in the install output;
		# block until the user is watching before systemd-cryptenroll starts.
		input('Are you ready to enroll your token? Press Enter to continue...')

		for dev in devices:
			info(f'Enrolling FIDO2 keyslot for {dev}')
			info('Touch the token when it blinks; a PIN prompt may appear first')
			try:
				# stdio stays inherited: the PIN/touch prompts are interactive
				subprocess.run(  # noqa: S603 - cmd is project-controlled list, not user input
					[  # noqa: S607 - systemd-cryptenroll from $PATH on the live ISO
						'systemd-cryptenroll',
						f'--unlock-key-file={key}',
						f'--fido2-device={token.path}',
						str(dev),
					],
					check=True,
				)
			except CalledProcessError as e:
				# stdio is inherited, cryptenroll's own error is already on screen
				warn(f'FIDO2 enrollment failed for {dev} (exit {e.returncode})')
			except FileNotFoundError as e:
				warn(f'FIDO2 enrollment failed for {dev}: {e}')
