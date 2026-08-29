# Print a password hash for use in a configuration file.
#
# Configs carry credentials hashed, never in plaintext: root_enc_password and
# users[].enc_password. The menu hashes what you type, so an unattended
# (--silent) install is the one path with nobody to type it, and writing that
# hash by hand meant calling crypt_yescrypt() yourself. This does it, with the
# same helper the menu uses, so the target's PAM sees the format it expects.
#
# With --config it writes the hash into the file's auth_config, so an
# unattended config can be filled in without hand-editing JSON around a
# pasted hash.
#
# Usage: python -m archinstoo --script passwd [--stdin]
#        python -m archinstoo --script passwd --config CONFIG --root
#        python -m archinstoo --script passwd --config CONFIG --user NAME

import argparse
import json
import sys
from getpass import getpass
from pathlib import Path

from archinstoo.lib.crypt import crypt_yescrypt


def _read_password(from_stdin: bool) -> str:
	if from_stdin:
		# for pipelines: password in, hash out, nothing on a tty
		return sys.stdin.readline().rstrip('\n')

	password = getpass('Password: ')

	if password != getpass('Repeat: '):
		sys.exit('error: passwords do not match')

	return password


def _write_config(path: Path, enc_password: str, root: bool, username: str | None) -> str:
	config = json.loads(path.read_text())
	# the shipped examples carry "auth_config": null, so setdefault is not
	# enough: an explicit null has to become a dict too
	auth = config.get('auth_config') or {}
	config['auth_config'] = auth

	if root:
		auth['root_enc_password'] = enc_password
		changed = 'root_enc_password'
	else:
		users = auth.get('users') or []
		auth['users'] = users
		user = next((u for u in users if u.get('username') == username), None)

		if user is None:
			# a config with no such user yet: create it unprivileged, the
			# menu's own default, and say so rather than guessing elev=True
			user = {'username': username, 'elev': False, 'groups': None, 'shell': 'bash'}
			users.append(user)
			print(f'added user {username} (elev: false)')

		user['enc_password'] = enc_password
		changed = f'users[{username}].enc_password'

	# write via a sibling temp file: a crash mid-write leaves the original
	# config intact instead of a truncated one
	tmp = path.with_suffix(path.suffix + '.tmp')
	tmp.write_text(json.dumps(config, indent=4) + '\n')
	tmp.replace(path)
	return changed


def passwd() -> None:
	parser = argparse.ArgumentParser(
		prog='python -m archinstoo --script passwd',
		description='Hash a password for root_enc_password / users[].enc_password in a config',
		suggest_on_error=True,
	)
	parser.add_argument(
		'--stdin',
		action='store_true',
		help='Read the password from stdin instead of prompting twice',
	)
	# positional, like the size/count scripts: the main parser owns --config
	parser.add_argument(
		'config',
		type=Path,
		nargs='?',
		help='Config to write the hash into (default: print the hash)',
	)
	target = parser.add_mutually_exclusive_group()
	target.add_argument('--root', action='store_true', help='Set root_enc_password')
	target.add_argument('--user', type=str, help='Set this user entry enc_password')

	args = parser.parse_args()

	if args.config and not (args.root or args.user):
		parser.error('a config needs --root or --user NAME')

	if not args.config and (args.root or args.user):
		parser.error('--root/--user only mean something with a config path')

	password = _read_password(args.stdin)

	if not password:
		sys.exit('error: empty password')

	enc_password = crypt_yescrypt(password)

	if not args.config:
		print(enc_password)
		return

	if not args.config.is_file():
		sys.exit(f'error: {args.config} not found')

	changed = _write_config(args.config, enc_password, args.root, args.user)
	print(f'{args.config}: {changed} set')


passwd()
