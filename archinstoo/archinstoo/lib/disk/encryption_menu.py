from typing import override

from archinstoo.lib.menu.abstract_menu import AbstractSubMenu
from archinstoo.lib.menu.menu_helper import MenuHelper
from archinstoo.lib.models.device import (
	DEFAULT_ITER_TIME,
	DeviceModification,
	DiskEncryption,
	EncryptionType,
	LvmConfiguration,
	LvmVolume,
	PartitionModification,
)
from archinstoo.lib.models.users import Password
from archinstoo.lib.output import FormattedOutput
from archinstoo.lib.translationhandler import tr
from archinstoo.lib.tui.curses_menu import EditMenu, SelectMenu
from archinstoo.lib.tui.menu_item import MenuItem, MenuItemGroup
from archinstoo.lib.tui.prompts import get_password
from archinstoo.lib.tui.result import ResultType
from archinstoo.lib.tui.types import Alignment, FrameProperties


class DiskEncryptionMenu(AbstractSubMenu[DiskEncryption]):
	def __init__(
		self,
		device_modifications: list[DeviceModification],
		lvm_config: LvmConfiguration | None = None,
		preset: DiskEncryption | None = None,
	):
		if preset:
			self._enc_config = preset
		else:
			self._enc_config = DiskEncryption()

		self._device_modifications = device_modifications
		self._lvm_config = lvm_config

		menu_options = self._define_menu_options()
		self._item_group = MenuItemGroup(menu_options, sort_items=False, checkmarks=True)

		super().__init__(
			self._item_group,
			self._enc_config,
			allow_reset=True,
		)

	def _define_menu_options(self) -> list[MenuItem]:
		return [
			MenuItem(
				text=tr('Encryption type'),
				action=lambda x: select_encryption_type(self._device_modifications, self._lvm_config, x),
				value=self._enc_config.encryption_type,
				preview_action=self._preview,
				key='encryption_type',
			),
			MenuItem(
				text=tr('Encryption password'),
				action=lambda x: select_encrypted_password(),
				value=self._enc_config.encryption_password,
				dependencies=[self._check_dep_enc_type],
				preview_action=self._preview,
				key='encryption_password',
			),
			MenuItem(
				text=tr('Iteration time'),
				action=select_iteration_time,
				value=self._enc_config.iter_time,
				dependencies=[self._check_dep_enc_type],
				preview_action=self._preview,
				key='iter_time',
			),
			MenuItem(
				text=tr('Partitions'),
				action=lambda x: select_partitions_to_encrypt(self._device_modifications, x),
				value=self._enc_config.partitions,
				dependencies=[self._check_dep_partitions],
				preview_action=self._preview,
				key='partitions',
			),
			MenuItem(
				text=tr('LVM volumes'),
				action=self._select_lvm_vols,
				value=self._enc_config.lvm_volumes,
				dependencies=[self._check_dep_lvm_vols],
				preview_action=self._preview,
				key='lvm_volumes',
			),
		]

	def _select_lvm_vols(self, preset: list[LvmVolume]) -> list[LvmVolume]:
		if self._lvm_config:
			return select_lvm_vols_to_encrypt(self._lvm_config, preset=preset)
		return []

	def _check_dep_enc_type(self) -> bool:
		enc_type: EncryptionType | None = self._item_group.find_by_key('encryption_type').value
		return bool(enc_type and enc_type != EncryptionType.NoEncryption)

	def _check_dep_partitions(self) -> bool:
		enc_type: EncryptionType | None = self._item_group.find_by_key('encryption_type').value
		return bool(enc_type and enc_type in [EncryptionType.Luks, EncryptionType.LvmOnLuks])

	def _check_dep_lvm_vols(self) -> bool:
		enc_type: EncryptionType | None = self._item_group.find_by_key('encryption_type').value
		return bool(enc_type and enc_type == EncryptionType.LuksOnLvm)

	@override
	def run(self, additional_title: str | None = None) -> DiskEncryption | None:
		super().run(additional_title=additional_title)

		enc_type: EncryptionType | None = self._item_group.find_by_key('encryption_type').value
		enc_password: Password | None = self._item_group.find_by_key('encryption_password').value
		iter_time: int | None = self._item_group.find_by_key('iter_time').value
		enc_partitions = self._item_group.find_by_key('partitions').value
		enc_lvm_vols = self._item_group.find_by_key('lvm_volumes').value

		if enc_type is None or enc_partitions is None or enc_lvm_vols is None:
			return None

		if enc_type in [EncryptionType.Luks, EncryptionType.LvmOnLuks] and enc_partitions:
			enc_lvm_vols = []

		if enc_type == EncryptionType.LuksOnLvm:
			enc_partitions = []

		if enc_type != EncryptionType.NoEncryption and enc_password and (enc_partitions or enc_lvm_vols):
			return DiskEncryption(
				encryption_password=enc_password,
				encryption_type=enc_type,
				partitions=enc_partitions,
				lvm_volumes=enc_lvm_vols,
				iter_time=iter_time or DEFAULT_ITER_TIME,
			)

		return None

	def _preview(self, item: MenuItem) -> str | None:
		output = ''

		if (enc_type := self._prev_type()) is not None:
			output += enc_type

		if (enc_pwd := self._prev_password()) is not None:
			output += f'\n{enc_pwd}'

		if (iter_time := self._prev_iter_time()) is not None:
			output += f'\n{iter_time}'

		if (partitions := self._prev_partitions()) is not None:
			output += f'\n\n{partitions}'

		if (lvm := self._prev_lvm_vols()) is not None:
			output += f'\n\n{lvm}'

		if not output:
			return None

		return output

	def _prev_type(self) -> str | None:
		if enc_type := self._item_group.find_by_key('encryption_type').value:
			enc_text = enc_type.type_to_text()
			return f'{tr("Encryption type")}: {enc_text}'

		return None

	def _prev_password(self) -> str | None:
		if enc_pwd := self._item_group.find_by_key('encryption_password').value:
			return f'{tr("Encryption password")}: {enc_pwd.hidden()}'

		return None

	def _prev_partitions(self) -> str | None:
		partitions: list[PartitionModification] | None = self._item_group.find_by_key('partitions').value

		if partitions:
			output = tr('Partitions to be encrypted') + '\n'
			output += FormattedOutput.as_table(partitions)
			return output.rstrip()

		return None

	def _prev_lvm_vols(self) -> str | None:
		volumes: list[PartitionModification] | None = self._item_group.find_by_key('lvm_volumes').value

		if volumes:
			output = tr('LVM volumes to be encrypted') + '\n'
			output += FormattedOutput.as_table(volumes)
			return output.rstrip()

		return None

	def _prev_iter_time(self) -> str | None:
		iter_time = self._item_group.find_by_key('iter_time').value
		enc_type = self._item_group.find_by_key('encryption_type').value

		if iter_time and enc_type != EncryptionType.NoEncryption:
			return f'{tr("Iteration time")}: {iter_time}ms'

		return None


def select_encryption_type(
	device_modifications: list[DeviceModification],
	lvm_config: LvmConfiguration | None = None,
	preset: EncryptionType | None = None,
) -> EncryptionType | None:
	options: list[EncryptionType] = []

	options = [EncryptionType.LvmOnLuks, EncryptionType.LuksOnLvm] if lvm_config else [EncryptionType.Luks]

	if not preset:
		preset = options[0]

	preset_value = preset.type_to_text()

	items = [MenuItem(o.type_to_text(), value=o) for o in options]
	group = MenuItemGroup(items)
	group.set_focus_by_value(preset_value)

	result = SelectMenu[EncryptionType](
		group,
		allow_skip=True,
		allow_reset=True,
		alignment=Alignment.CENTER,
		frame=FrameProperties.min(tr('Encryption type')),
	).run()

	match result.type_:
		case ResultType.Reset:
			return None
		case ResultType.Skip:
			return preset
		case ResultType.Selection:
			return result.get_value()


def select_encrypted_password() -> Password | None:
	header = tr('Enter disk encryption password (leave blank for no encryption)') + '\n'
	return get_password(
		text=tr('Disk encryption password'),
		header=header,
		allow_skip=True,
	)


def select_partitions_to_encrypt(
	modification: list[DeviceModification],
	preset: list[PartitionModification],
) -> list[PartitionModification]:
	partitions: list[PartitionModification] = []

	# do not allow encrypting the EFI system partition
	for mod in modification:
		partitions += [p for p in mod.partitions if not p.is_efi()]

	# do not allow encrypting existing partitions that are not marked as wipe
	avail_partitions = [p for p in partitions if not p.exists()]

	if avail_partitions:
		group = MenuHelper(data=avail_partitions).create_menu_group()
		group.set_selected_by_value(preset)

		result = SelectMenu[PartitionModification](
			group,
			alignment=Alignment.CENTER,
			multi=True,
			allow_skip=True,
		).run()

		match result.type_:
			case ResultType.Reset:
				return []
			case ResultType.Skip:
				return preset
			case ResultType.Selection:
				return result.get_values()

	return []


def select_lvm_vols_to_encrypt(
	lvm_config: LvmConfiguration,
	preset: list[LvmVolume],
) -> list[LvmVolume]:
	volumes: list[LvmVolume] = lvm_config.get_all_volumes()

	if volumes:
		group = MenuHelper(data=volumes).create_menu_group()

		result = SelectMenu[LvmVolume](
			group,
			alignment=Alignment.CENTER,
			multi=True,
		).run()

		match result.type_:
			case ResultType.Reset:
				return []
			case ResultType.Skip:
				return preset
			case ResultType.Selection:
				return result.get_values()

	return []


def select_iteration_time(preset: int | None = None) -> int | None:
	header = tr('Enter iteration time for LUKS encryption (in milliseconds)') + '\n'
	header += tr('Higher values increase security but slow down boot time') + '\n'
	header += tr(f'Default: {DEFAULT_ITER_TIME}ms, Recommended range: 1000-60000') + '\n'

	def validate_iter_time(value: str | None) -> str | None:
		if not value:
			return None

		try:
			iter_time = int(value)
			if iter_time < 100:
				return tr('Iteration time must be at least 100ms')
			if iter_time > 120000:
				return tr('Iteration time must be at most 120000ms')
			return None
		except ValueError:
			return tr('Please enter a valid number')

	result = EditMenu(
		tr('Iteration time'),
		header=header,
		alignment=Alignment.CENTER,
		allow_skip=True,
		default_text=str(preset) if preset else str(DEFAULT_ITER_TIME),
		validator=validate_iter_time,
	).input()

	match result.type_:
		case ResultType.Skip:
			return preset
		case ResultType.Selection:
			if not result.text():
				return preset
			return int(result.text())
		case ResultType.Reset:
			return None
