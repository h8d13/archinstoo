from dataclasses import dataclass
from typing import Any, Self

from archinstoo.lib.localization.utils import get_kb_layout


@dataclass
class LocaleConfiguration:
	kb_layout: str
	sys_lang: str
	sys_enc: str
	console_font: str = 'default8x16'
	# Graphical (X11/Wayland) keyboard, kept separate from the console kb_layout.
	# Empty = leave unset (graphical sessions fall back to the libxkbcommon 'us').
	# xkb_options is a comma-separated list (matches XkbOptions / XKB_DEFAULT_OPTIONS).
	xkb_layout: str = ''
	xkb_model: str = ''
	xkb_variant: str = ''
	xkb_options: str = ''

	@classmethod
	def default(cls) -> Self:
		layout = get_kb_layout()
		if layout == '':
			layout = 'us'
		return cls(layout, 'en_US.UTF-8', 'UTF-8')

	def json(self) -> dict[str, str]:
		return {
			'kb_layout': self.kb_layout,
			'sys_lang': self.sys_lang,
			'sys_enc': self.sys_enc,
			'console_font': self.console_font,
			'xkb_layout': self.xkb_layout,
			'xkb_model': self.xkb_model,
			'xkb_variant': self.xkb_variant,
			'xkb_options': self.xkb_options,
		}

	def preview(self) -> str:
		output = '{}: {}\n'.format('Keyboard layout', self.kb_layout)
		output += '{}: {}\n'.format('Locale language', self.sys_lang)
		output += '{}: {}\n'.format('Locale encoding', self.sys_enc)
		output += '{}: {}'.format('Console font', self.console_font)
		if self.xkb_layout:
			xkb = self.xkb_layout
			if self.xkb_variant:
				xkb += f' ({self.xkb_variant})'
			output += '\n' + '{}: {}'.format('Graphical layout', xkb)
			if self.xkb_model:
				output += '\n' + '{}: {}'.format('Keyboard model', self.xkb_model)
			if self.xkb_options:
				output += '\n' + '{}: {}'.format('XKB options', self.xkb_options)
		return output

	def _load_config(self, args: dict[str, str]) -> None:
		if 'sys_lang' in args:
			self.sys_lang = args['sys_lang']
		if 'sys_enc' in args:
			self.sys_enc = args['sys_enc']
		if 'kb_layout' in args:
			self.kb_layout = args['kb_layout']
		if 'console_font' in args:
			self.console_font = args['console_font']
		if 'xkb_layout' in args:
			self.xkb_layout = args['xkb_layout']
		if 'xkb_model' in args:
			self.xkb_model = args['xkb_model']
		if 'xkb_variant' in args:
			self.xkb_variant = args['xkb_variant']
		if 'xkb_options' in args:
			self.xkb_options = args['xkb_options']

	@classmethod
	def parse_arg(cls, args: dict[str, Any]) -> Self:
		default = cls.default()

		if 'locale_config' in args:
			default._load_config(args['locale_config'])
		else:
			default._load_config(args)

		return default
