from typing import TYPE_CHECKING

from archinstoo.lib.args import get_arch_config_handler
from archinstoo.lib.models.application import terminal_for
from archinstoo.lib.output import warn

if TYPE_CHECKING:
	from pathlib import Path

	from archinstoo.lib.installer import Installer
	from archinstoo.lib.models.users import User


# One terminal choice for every profile that needs one. The user picks it in
# the application menu, which installs the package and exports TERMINAL in
# /etc/environment (pam_env puts that in the session).
#
# Three ways a WM ends up launching it:
#   - i3 and labwc call i3-sensible-terminal / lab-sensible-terminal, both of
#     which try $TERMINAL before their own fallback lists. Nothing to patch.
#   - qtile's guess_terminal() ignores $TERMINAL and walks a fixed list, on
#     which foot only appears under Wayland. The profile writes the shipped
#     default config with the pick passed in as the preference argument, which
#     is tried before that list.
#   - the rest hardcode a binary in a config we own or rewrite, and call
#     terminal_command() at provision time.
#
# xmonad is the holdout: its terminal is compiled into XMonad/Config.hs and
# changing it needs a ghc rebuild, so that profile keeps xterm.
def terminal_command() -> str:
	return terminal_for(get_arch_config_handler().config.app_config)


def swap_terminal(text: str, hardcoded: str, source: Path, template: str = '{terminal}') -> str:
	# upstream renames its default terminal from time to time. a silent no-op
	# here would leave the keybind pointing at a package we no longer install,
	# so say so instead of shipping a dead binding
	terminal = terminal_command()

	if hardcoded not in text:
		warn(f'{source}: no "{hardcoded}" to repoint at {terminal}, left as shipped')
		return text

	# most configs name the binary bare; template covers the ones that want it
	# wrapped in a call or quoted
	return text.replace(hardcoded, template.format(terminal=terminal))


def provision_terminal_config(
	install_session: Installer,
	users: list[User],
	shipped: Path,
	config_path: str,
	hardcoded: str,
	executable: bool = False,
	template: str = '{terminal}',
) -> None:
	# hyprland and niri both copy their shipped default into ~/.config on first
	# run, so the repointed copy has to be there before that happens. river
	# never copies: no init means no bindings and no layout, a black screen
	if not shipped.is_file():
		warn(f'{shipped} missing, leaving the config to first run')
		return

	conf = swap_terminal(shipped.read_text(), hardcoded, shipped, template)

	for user in users:
		dest = install_session.target / 'home' / user.username / '.config' / config_path
		dest.parent.mkdir(parents=True, exist_ok=True)
		dest.write_text(conf)
		if executable:
			# river runs init as a program, a 0644 copy is silently skipped
			dest.chmod(0o755)

		install_session.chown_tree(user.username, f'/home/{user.username}/.config')
