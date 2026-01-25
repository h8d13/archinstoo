import ctypes
import ctypes.util
import secrets
import string
from pathlib import Path
from typing import cast

from ..output import debug

# Base64-like alphabet used by crypt salt
SALT_CHARS = string.ascii_letters + string.digits + './'


def _load_libcrypt() -> ctypes.CDLL:
	# Use find_library for portable library discovery
	lib_path = ctypes.util.find_library('crypt')
	if lib_path:
		return ctypes.CDLL(lib_path)

	# Fallback: try versioned names
	for name in ('libcrypt.so.2', 'libcrypt.so.1', 'libcrypt.so'):
		try:
			return ctypes.CDLL(name)
		except OSError:
			continue

	# On musl (Alpine), crypt() is in libc itself
	libc_path = ctypes.util.find_library('c')
	if libc_path:
		return ctypes.CDLL(libc_path)

	raise OSError('Could not find libcrypt or libc with crypt() support')


libcrypt = _load_libcrypt()

libcrypt.crypt.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
libcrypt.crypt.restype = ctypes.c_char_p

# Check if crypt_gensalt is available (not on musl)
_has_crypt_gensalt = hasattr(libcrypt, 'crypt_gensalt')
if _has_crypt_gensalt:
	libcrypt.crypt_gensalt.argtypes = [ctypes.c_char_p, ctypes.c_ulong, ctypes.c_char_p, ctypes.c_int]
	libcrypt.crypt_gensalt.restype = ctypes.c_char_p

LOGIN_DEFS = Path('/etc/login.defs')


def _search_login_defs(key: str) -> str | None:
	if not LOGIN_DEFS.exists():
		return None

	defs = LOGIN_DEFS.read_text()
	for line in defs.split('\n'):
		line = line.strip()

		if line.startswith('#'):
			continue

		if line.startswith(key):
			value = line.split(' ')[1]
			return value

	return None


def _gen_salt_chars(length: int) -> str:
	return ''.join(secrets.choice(SALT_CHARS) for _ in range(length))


def crypt_gen_salt(prefix: str | bytes, rounds: int) -> bytes:
	if isinstance(prefix, str):
		prefix = prefix.encode('utf-8')

	# Use crypt_gensalt if available (glibc/libxcrypt)
	if _has_crypt_gensalt:
		setting = libcrypt.crypt_gensalt(prefix, rounds, None, 0)
		if setting is None:
			raise ValueError(f'crypt_gensalt() returned NULL for prefix {prefix!r} and rounds {rounds}')
		return cast(bytes, setting)

	# Python fallback for musl
	prefix_str = prefix.decode('utf-8')

	if prefix_str == '$y$':
		# yescrypt: $y$j<params>$<salt>
		# params encode cost - use simplified format
		# Cost 5 default -> 'j9T' is common
		cost_char = chr(ord('7') + rounds - 4) if rounds >= 4 else '5'
		return f'$y$j{cost_char}T${_gen_salt_chars(22)}'.encode('utf-8')
	elif prefix_str == '$6$':
		# SHA-512: $6$rounds=N$<salt>
		return f'$6$rounds={rounds}${_gen_salt_chars(16)}'.encode('utf-8')
	elif prefix_str == '$5$':
		# SHA-256: $5$rounds=N$<salt>
		return f'$5$rounds={rounds}${_gen_salt_chars(16)}'.encode('utf-8')
	else:
		raise ValueError(f'Unsupported prefix: {prefix_str}')


def crypt_yescrypt(plaintext: str) -> str:
	"""
	By default chpasswd in Arch uses PAM to hash the password with crypt_yescrypt
	the PAM code https://github.com/linux-pam/linux-pam/blob/master/modules/pam_unix/support.c
	shows that the hashing rounds are determined from YESCRYPT_COST_FACTOR in /etc/login.defs
	If no value was specified (or commented out) a default of 5 is chosen
	"""
	if (value := _search_login_defs('YESCRYPT_COST_FACTOR')) is not None:
		rounds = int(value)
		if rounds < 3:
			rounds = 3
		elif rounds > 11:
			rounds = 11
	else:
		rounds = 5

	debug(f'Creating yescrypt hash with rounds {rounds}')

	enc_plaintext = plaintext.encode('utf-8')
	salt = crypt_gen_salt('$y$', rounds)

	crypt_hash = libcrypt.crypt(enc_plaintext, salt)

	# musl's crypt() doesn't support yescrypt, fallback to SHA-512
	if crypt_hash is None or crypt_hash == b'*0' or crypt_hash == b'*1':
		debug('yescrypt not supported, falling back to SHA-512')
		salt = crypt_gen_salt('$6$', 5000)
		crypt_hash = libcrypt.crypt(enc_plaintext, salt)

	if crypt_hash is None:
		raise ValueError('crypt() returned NULL')

	return cast(bytes, crypt_hash).decode('utf-8')
