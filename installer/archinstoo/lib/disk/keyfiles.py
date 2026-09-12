import os
from typing import TYPE_CHECKING

from archinstoo.lib.disk.luks import KEYFILE_DIR, Luks2
from archinstoo.lib.models.device import BOOT_ITER_TIME, BOOT_PBKDF_MEMORY, DiskEncryption, EncryptionType
from archinstoo.lib.output import debug

if TYPE_CHECKING:
	from pathlib import Path


class KeyFileGenerator:
	# keyfiles and crypttab entries for the non-root LUKS devices, plus the
	# root auto-unlock slot sd-encrypt picks up from /etc/cryptsetup-keys.d
	def __init__(self, target: Path, disk_encryption: DiskEncryption) -> None:
		self.target = target
		self._disk_encryption = disk_encryption
		self._files: list[str] = []

	def generate(self) -> list[str]:
		# returns the in-target keyfile paths mkinitcpio FILES must embed
		match self._disk_encryption.encryption_type:
			case EncryptionType.LUKS:
				self._generate_key_files_partitions()
			case EncryptionType.LUKS_ON_LVM:
				self._generate_key_file_lvm_volumes()
			case EncryptionType.NO_ENCRYPTION:
				pass
			case EncryptionType.LVM_ON_LUKS:
				# LvmOnLuks: the LUKS container holds an LVM PV, root is a volume inside it.
				# The partition itself isn't "root", so _generate_key_files_partitions
				# can't detect it via is_root(). Handle it directly here.
				if self._disk_encryption.auto_unlock_root:
					for part_mod in self._disk_encryption.partitions:
						if part_mod.is_boot() or part_mod.is_efi():
							continue
						luks_handler = Luks2(
							part_mod.safe_dev_path,
							mapper_name=part_mod.mapper_name,
							password=self._disk_encryption.encryption_password,
						)
						self._create_root_keyfile(luks_handler, mapper_name='cryptlvm')
						break
		return self._files

	def _generate_key_files_partitions(self) -> None:
		root_is_encrypted = any(p.is_root() for p in self._disk_encryption.partitions)

		for part_mod in self._disk_encryption.partitions:
			gen_enc_file = self._disk_encryption.should_generate_encryption_file(part_mod)

			luks_handler = Luks2(
				part_mod.safe_dev_path,
				mapper_name=part_mod.mapper_name,
				password=self._disk_encryption.encryption_password,
			)

			if gen_enc_file and not part_mod.is_root():
				debug(f'Creating key-file: {part_mod.dev_path}')
				if root_is_encrypted and not part_mod.luks_mapper:  # pre-opened: no passphrase to derive from
					# GRUB has limited memory for argon2 decryption;
					# constrain the keyfile slot too so GRUB can handle it
					is_boot = part_mod.is_boot()
					uses_argon2 = self._disk_encryption.pbkdf.is_argon2
					pbkdf_memory = BOOT_PBKDF_MEMORY if is_boot and uses_argon2 else None
					iter_time = BOOT_ITER_TIME if is_boot else self._disk_encryption.iter_time
					luks_handler.create_keyfile(
						self.target,
						pbkdf_memory=pbkdf_memory,
						iter_time=iter_time,
						pbkdf=self._disk_encryption.pbkdf,
					)
				else:
					# unencrypted root (keyfile would sit in plaintext) or pre-opened: prompt via crypttab
					luks_handler.create_crypttab_entry(self.target)

			if self._disk_encryption.auto_unlock_root and part_mod.is_root():
				self._create_root_keyfile(luks_handler)

	def _generate_key_file_lvm_volumes(self) -> None:
		root_is_encrypted = any(v.is_root() for v in self._disk_encryption.lvm_volumes)

		for vol in self._disk_encryption.lvm_volumes:
			gen_enc_file = self._disk_encryption.should_generate_encryption_file(vol)

			luks_handler = Luks2(
				vol.safe_dev_path,
				mapper_name=vol.mapper_name,
				password=self._disk_encryption.encryption_password,
			)

			if gen_enc_file and not vol.is_root():
				debug(f'Creating key-file: {vol.dev_path}')
				if root_is_encrypted:
					luks_handler.create_keyfile(
						self.target,
						iter_time=self._disk_encryption.iter_time,
						pbkdf=self._disk_encryption.pbkdf,
					)
				else:
					luks_handler.create_crypttab_entry(self.target)

			if self._disk_encryption.auto_unlock_root and vol.is_root():
				self._create_root_keyfile(luks_handler)

	def _create_root_keyfile(self, luks_handler: Luks2, mapper_name: str = 'root') -> None:
		# sd-encrypt standard path and add it as a LUKS
		# key slot so the volume can be auto-unlocked from the initramfs.
		# sd-encrypt auto-detects keys at /etc/cryptsetup-keys.d/<name>.key.
		kf_path = KEYFILE_DIR / f'{mapper_name}.key'
		keyfile = self.target / kf_path.relative_to('/')

		debug(f'Creating key-file: {keyfile}')
		keyfile.parent.mkdir(parents=True, exist_ok=True)
		keyfile.write_bytes(os.urandom(2048))
		keyfile.chmod(0o000)

		# initramfs unlocks this slot on the host CPU, user's iter_time applies
		luks_handler.add_key(
			keyfile,
			iter_time=self._disk_encryption.iter_time,
			pbkdf=self._disk_encryption.pbkdf,
		)

		if str(kf_path) not in self._files:
			self._files.append(str(kf_path))
