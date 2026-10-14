from archinstoo.lib.hardware import SysInfo
from archinstoo.lib.models.bootloader import GRUB_ESP, Bootloader, BootloaderConfiguration
from archinstoo.lib.models.device import DiskLayoutConfiguration, DiskLayoutType, PartitionFlag, PartitionTable, has_separate_boot
from archinstoo.lib.utils.env import Os


def validate_bootloader(
	bootloader_config: BootloaderConfiguration | None,
	disk_config: DiskLayoutConfiguration | None,
	uefi: bool,
) -> list[str]:
	# Single pre-flight gate on purpose, disk-shape rules included: a second
	# validate function is one the menu or --silent path forgets to call.
	errors: list[str] = []

	if not bootloader_config or bootloader_config.bootloader is None:
		return errors

	bootloader = bootloader_config.bootloader

	if disk_config is None:
		return ['No disk layout selected']

	# lsblk only reports mounts inside the installer's root: under BOOT that
	# is the host's /mnt alone, anything else looks empty
	if disk_config.config_type == DiskLayoutType.Pre_mount and not disk_config.device_modifications:
		hint = " (BOOT passes only the host's /mnt through)" if Os.running_from_bootstrap() else ''
		return [f'Nothing mounted at {disk_config.mountpoint}{hint}']

	# an LVM root is a volume, not a partition
	root = disk_config.get_root()
	boot_partition = disk_config.get_boot_partition()
	efi_partition = disk_config.get_efi_partition() if uefi else None

	if root is None:
		errors.append('Root partition not found')

	# Legacy vs /efi newer standard
	if uefi:
		if efi_partition is None:
			errors.append('EFI system partition (ESP) not found')
		elif efi_partition.fs_type is None or not efi_partition.fs_type.is_fat():
			errors.append('ESP must be formatted as a FAT filesystem')
	elif boot_partition is None:
		errors.append('Boot partition not found')

	# Table-vs-firmware pre-flight: parted only rejects these while
	# partitioning, after the disk wipe has already started
	default_table = PartitionTable.GPT if uefi else PartitionTable.MBR
	for layout in disk_config.device_modifications:
		gpt = layout.using_gpt(default_table)
		has_bios_grub = any(PartitionFlag.BIOS_GRUB in p.flags for p in layout.partitions)
		if not gpt and has_bios_grub:
			errors.append('bios_grub flag requires a GPT partition table (msdos label selected)')
		if not uefi and bootloader == Bootloader.Grub and gpt and not has_bios_grub:
			errors.append('BIOS boot from a GPT disk needs a 1MiB bios_grub partition')
		if layout.wipe and not gpt and len(layout.partitions) > 3:
			errors.append('Too many partitions on disk, MBR disks can only have 3 primary partitions')

	# signed GRUB only opens LUKS1 or pbkdf2 LUKS2, and the containers here
	# are argon2 LUKS2, so /boot stays in the clear for every loader
	if disk_config.disk_encryption and any(p.is_boot() for p in disk_config.disk_encryption.partitions):
		errors.append('Encrypted /boot is not supported')

	# When ESP is at /efi with no separate /boot (e.g. btrfs subvolumes),
	# systemd-boot has no partition to find the kernel/initramfs;
	# either UKI must be enabled or a separate /boot (XBOOTLDR) is needed
	if bootloader == Bootloader.Systemd and efi_partition and not boot_partition and not bootloader_config.uki:
		errors.append('systemd-boot with ESP at /efi requires UKI or a separate XBOOTLDR /boot partition')

	# systemd-boot reads a separate /boot through EFI's SFSP (FAT only) and
	# finds it by partition type GUID. bootctl verifies the GUID but never
	# the filesystem, so an ext4 XBOOTLDR installs cleanly and then boots
	# into an empty menu. A UKI is self-contained on the ESP, so bootctl is
	# never told about the boot partition and neither rule applies.
	if bootloader == Bootloader.Systemd and boot_partition is not None and not bootloader_config.uki and has_separate_boot(boot_partition, efi_partition):
		if boot_partition.fs_type is None or not boot_partition.fs_type.is_fat():
			errors.append('systemd-boot requires a FAT /boot partition')
		if not boot_partition.is_xbootldr():
			errors.append('A separate /boot for systemd-boot must be marked XBOOTLDR')

	if not bootloader.has_bios_support() and not SysInfo.has_uefi():
		errors.append(f'{bootloader.display_name()} requires a UEFI system')

	# Fedora's shim and signed grubx64.efi install into /boot/efi/EFI/fedora
	# from the RPMs themselves; an ESP mounted anywhere else never sees them
	# https://docs.fedoraproject.org/en-US/quick-docs/grub2-bootloader/#create-a-grub-2-configuration
	if bootloader == Bootloader.Grub and uefi and efi_partition is not None and efi_partition.mountpoint != GRUB_ESP:
		errors.append(f'GRUB on UEFI needs the ESP mounted at {GRUB_ESP} (found {efi_partition.mountpoint})')

	if bootloader.requires_uki() and not bootloader_config.uki:
		errors.append(f'{bootloader.display_name()} boots a unified kernel image: enable UKI')

	# kernel-install puts UKIs on an XBOOTLDR /boot when there is one, where
	# the firmware never looks
	if bootloader == Bootloader.Efistub and boot_partition is not None and has_separate_boot(boot_partition, efi_partition):
		errors.append('Efistub needs the UKIs on the ESP: no separate /boot partition')

	if bootloader_config.uki and not bootloader.has_uki_support():
		errors.append(f'{bootloader.display_name()} does not boot unified kernel images')

	return errors
