from archinstoo.lib.hardware import SysInfo
from archinstoo.lib.models.bootloader import Bootloader, BootloaderConfiguration
from archinstoo.lib.models.device import DiskLayoutConfiguration, PartitionFlag, PartitionModification, PartitionTable, has_separate_boot


def validate_bootloader(
	bootloader_config: BootloaderConfiguration | None,
	disk_config: DiskLayoutConfiguration | None,
	uefi: bool,
) -> list[str]:
	# Checks the selected bootloader is valid for the selected filesystem type
	# of the boot partition. Returns error messages, empty if the config is
	# valid. Kept free of menu state so --silent can run it too: every one of
	# these otherwise surfaces as a failed install or an unbootable system.
	errors: list[str] = []

	if not bootloader_config or bootloader_config.bootloader is None:
		return errors

	bootloader = bootloader_config.bootloader

	if disk_config is None:
		return ['No disk layout selected']

	root_partition: PartitionModification | None = None
	boot_partition: PartitionModification | None = None
	efi_partition: PartitionModification | None = None

	for layout in disk_config.device_modifications:
		if root_partition := layout.get_root_partition():
			break
	for layout in disk_config.device_modifications:
		if boot_partition := layout.get_boot_partition():
			break
	if uefi:
		for layout in disk_config.device_modifications:
			if efi_partition := layout.get_efi_partition():
				break

	if root_partition is None:
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

	if disk_config.disk_encryption and bootloader != Bootloader.Grub:
		enc = disk_config.disk_encryption
		if any(p.is_boot() for p in enc.partitions):
			errors.append('Encrypted /boot is only supported with GRUB')

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

	if bootloader in (Bootloader.Systemd, Bootloader.Efistub, Bootloader.Refind) and not SysInfo.has_uefi():
		errors.append(f'{bootloader.display_name()} requires a UEFI system')

	# Firmware reads the kernel directly from the boot partition, which must be FAT.
	if bootloader == Bootloader.Efistub and boot_partition is not None and (boot_partition.fs_type is None or not boot_partition.fs_type.is_fat()):
		errors.append('Efistub does not support booting with a non-FAT boot partition')

	if bootloader == Bootloader.Limine:
		limine_boot = boot_partition or efi_partition
		if limine_boot is not None and (limine_boot.fs_type is None or not limine_boot.fs_type.is_fat()):
			errors.append('Limine does not support booting with a non-FAT boot partition')

		# Nothing mounted at /boot means the kernels sit on the root
		# filesystem, which limine cannot read (FAT12/16/32 and ISO9660 only).
		# The old form asked `efi == boot and efi.mountpoint != /boot`, which
		# is self-contradictory: get_boot_partition() matches on mountpoint
		# == /boot, so that never fired.
		if not bootloader_config.uki and efi_partition is not None and boot_partition is None:
			errors.append(
				f'Limine requires kernels on a FAT partition. The ESP is mounted at {efi_partition.mountpoint}, '
				'enable UKI or add a separate /boot partition to install Limine.'
			)

	return errors
