from typing import TYPE_CHECKING

from archinstoo.lib.exceptions import SysCallError
from archinstoo.lib.localization.utils import locale_encoding, split_locale_name, uncomment_locale
from archinstoo.lib.output import debug, error, info

if TYPE_CHECKING:
	from pathlib import Path

	from archinstoo.lib.installer import Installer
	from archinstoo.lib.models.locale import LocaleConfiguration

# writes the target's locale, console and graphical keyboard files; the
# listings and validation the menus use live in utils.py


def set_locale(installation: Installer, locale_config: LocaleConfiguration) -> bool:
	# the menu keeps language and encoding apart; locale.gen names them
	# together, so the same splitting the encoding menu scopes itself by
	lang, _, modifier = split_locale_name(locale_config.sys_lang)
	encoding = locale_encoding(locale_config.sys_lang, locale_config.sys_enc)

	locale_gen = installation.target / 'etc/locale.gen'
	locale_gen_lines = locale_gen.read_text().splitlines(True)

	if not uncomment_locale(locale_gen_lines, locale_config.sys_lang, locale_config.sys_enc):
		error(f"Invalid locale: language '{locale_config.sys_lang}', encoding '{locale_config.sys_enc}'")
		return False
	# tools hardcoding LC_ALL=en_US.UTF-8 warn on every non-US system otherwise
	# https://github.com/archlinux/archinstall/issues/3764
	uncomment_locale(locale_gen_lines, 'en_US.UTF-8', 'UTF-8')
	locale_gen.write_text(''.join(locale_gen_lines))

	try:
		installation.arch_chroot('locale-gen')
	except SysCallError as e:
		error(f'Failed to run locale-gen on target: {e}')
		return False

	# always fully qualified: bare SUPPORTED entries ("en_IL UTF-8") compile
	# under the bare name, but localedef also registers a normalized-codeset
	# alias (locarchive.c), so LANG=en_IL.UTF-8 resolves and UTF-8 stays
	# visible to tools sniffing LANG (tmux et al.)
	(installation.target / 'etc/locale.conf').write_text(f'LANG={lang}.{encoding}{modifier}\n')
	info(f'Set locale LANG={lang}.{encoding}{modifier}')
	return True


def set_vconsole(installation: Installer, locale_config: LocaleConfiguration) -> None:
	kb_vconsole: str = locale_config.kb_layout
	font_vconsole: str = locale_config.console_font

	vconsole_dir: Path = installation.target / 'etc'
	vconsole_dir.mkdir(parents=True, exist_ok=True)
	vconsole_path: Path = vconsole_dir / 'vconsole.conf'

	vconsole_content = f'KEYMAP={kb_vconsole}\n'
	vconsole_content += f'FONT={font_vconsole}\n'

	vconsole_path.write_text(vconsole_content)
	info(f'Wrote to {vconsole_path} using {kb_vconsole} and {font_vconsole}')


def set_keyboard(installation: Installer, locale_config: LocaleConfiguration) -> bool:
	# Graphical (X11/Wayland) keyboard config, separate from the console
	# keymap in vconsole.conf. Writes the Xorg InputClass (00-keyboard.conf)
	# and the libxkbcommon env Wayland compositors read (XKB_DEFAULT_*).
	# No-op unless a layout is set, leaving graphical sessions at the
	# libxkbcommon 'us' default. Selections come pre-validated from the menu.
	layout = locale_config.xkb_layout
	if not layout.strip():
		debug('No graphical (XKB) keyboard layout set, skipping')
		return False

	model = locale_config.xkb_model
	variant = locale_config.xkb_variant
	options = locale_config.xkb_options

	# Xorg: only emit the Options that are set (layout always, rest optional)
	xorg_opts = [('XkbLayout', layout)]
	if model:
		xorg_opts.append(('XkbModel', model))
	if variant:
		xorg_opts.append(('XkbVariant', variant))
	if options:
		xorg_opts.append(('XkbOptions', options))

	opt_lines = '\n'.join(f'    Option "{k}" "{v}"' for k, v in xorg_opts)
	content = f'Section "InputClass"\n    Identifier "system-keyboard"\n    MatchIsKeyboard "on"\n{opt_lines}\nEndSection\n'

	xorg_conf_dir = installation.target / 'etc/X11/xorg.conf.d'
	xorg_conf_dir.mkdir(parents=True, exist_ok=True)
	(xorg_conf_dir / '00-keyboard.conf').write_text(content)
	info(f'Wrote X11 keyboard config: layout={layout} variant={variant or "-"}')

	# Wayland: libxkbcommon ignores vconsole.conf and 00-keyboard.conf,
	# so the layout has to reach the session as env vars.
	env_vars = {'XKB_DEFAULT_LAYOUT': layout}
	if model:
		env_vars['XKB_DEFAULT_MODEL'] = model
	if variant:
		env_vars['XKB_DEFAULT_VARIANT'] = variant
	if options:
		env_vars['XKB_DEFAULT_OPTIONS'] = options

	installation.set_environment(env_vars)

	return True
