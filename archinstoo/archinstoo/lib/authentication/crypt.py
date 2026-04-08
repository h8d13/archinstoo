import ctypes
import ctypes.util
import secrets
import string
from pathlib import Path
from typing import cast

from archinstoo.lib.output import debug

# Base64-like alphabet used by crypt() salt strings
SALT_CHARS = string.ascii_letters + string.digits + './'


def _load_libcrypt() -> ctypes.CDLL:
	"""Locate and load the crypt library, handling both glibc and musl environments."""
	# Standard discovery — works on most distros
	lib_path = ctypes.util.find_library('crypt')
	if lib_path:
		return ctypes.CDLL(lib_path)

	# Try versioned names explicitly (some distros skip the unversioned symlink)
	for name in ('libcrypt.so.2', 'libcrypt.so.1', 'libcrypt.so'):
		try:
			return ctypes.CDLL(name)
		except OSError:
			continue

	# On musl (Alpine), crypt() lives inside libc itself — no separate libcrypt
	libc_path = ctypes.util.find_library('c')
	if libc_path:
		return ctypes.CDLL(libc_path)

	raise OSError('Could not find libcrypt or libc with crypt() support')


def _symbol_exists(lib: ctypes.CDLL, name: str) -> bool:
	"""
	Check if a symbol actually exists in the loaded library.

	NOTE: hasattr(cdll, name) is always True in ctypes because attribute access
	creates a lazy function object without resolving the symbol.  We must use
	subscript notation (lib[name]) which calls dlsym() immediately.
	"""
	try:
		_addr = lib[name]  # raises AttributeError if symbol is absent (unlike hasattr/getattr)
		return bool(_addr)
	except AttributeError:
		return False


libcrypt = _load_libcrypt()

libcrypt.crypt.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
libcrypt.crypt.restype = ctypes.c_char_p

# crypt_gensalt is provided by libxcrypt (glibc) but absent on musl
_has_crypt_gensalt = _symbol_exists(libcrypt, 'crypt_gensalt')
if _has_crypt_gensalt:
	libcrypt.crypt_gensalt.argtypes = [ctypes.c_char_p, ctypes.c_ulong, ctypes.c_char_p, ctypes.c_int]
	libcrypt.crypt_gensalt.restype = ctypes.c_char_p

LOGIN_DEFS = Path('/etc/login.defs')


def _search_login_defs(key: str) -> str | None:
	if not LOGIN_DEFS.exists():
		return None

	for line in LOGIN_DEFS.read_text().splitlines():
		line = line.strip()
		if line.startswith('#'):
			continue
		if line.startswith(key):
			return line.split()[1]

	return None


def _gen_salt_chars(length: int) -> str:
	return ''.join(secrets.choice(SALT_CHARS) for _ in range(length))


def crypt_gen_salt(prefix: str | bytes, rounds: int) -> bytes:
	if isinstance(prefix, str):
		prefix = prefix.encode('utf-8')

	# Prefer the library's own generator when available (glibc / libxcrypt)
	if _has_crypt_gensalt:
		setting = libcrypt.crypt_gensalt(prefix, rounds, None, 0)
		if setting is None:
			raise ValueError(f'crypt_gensalt() returned NULL for prefix {prefix!r} and rounds {rounds}')
		return cast(bytes, setting)

	# Pure-Python fallback for musl (no crypt_gensalt)
	prefix_str = prefix.decode('utf-8')

	if prefix_str == '$y$':
		# yescrypt: musl doesn't support it anyway — crypt_yescrypt() will detect
		# the failure sentinel and fall back to SHA-512 after calling us.
		# We still produce a structurally valid salt so the call path is exercised.
		return f'$y$j9T${_gen_salt_chars(22)}'.encode()
	if prefix_str == '$6$':
		# SHA-512
		return f'$6$rounds={rounds}${_gen_salt_chars(16)}'.encode()
	if prefix_str == '$5$':
		# SHA-256
		return f'$5$rounds={rounds}${_gen_salt_chars(16)}'.encode()
	raise ValueError(f'Unsupported prefix: {prefix_str!r}')


def crypt_yescrypt(plaintext: str) -> str:
	"""
	Hash a password with yescrypt (the Arch Linux default via PAM/chpasswd).

	Falls back to SHA-512 on musl systems where yescrypt is not supported.
	The YESCRYPT_COST_FACTOR from /etc/login.defs is honoured when present;
	the PAM default of 5 is used otherwise.
	"""
	if (value := _search_login_defs('YESCRYPT_COST_FACTOR')) is not None:
		rounds = max(3, min(11, int(value)))
	else:
		rounds = 5

	debug(f'Creating yescrypt hash with rounds {rounds}')

	enc_plaintext = plaintext.encode('utf-8')
	salt = crypt_gen_salt('$y$', rounds)
	crypt_hash = libcrypt.crypt(enc_plaintext, salt)

	# musl doesn't return *0/*1 for unknown algorithms — it falls through to DES,
	# which produces a hash that doesn't start with $y$.  Check the prefix too.
	if crypt_hash is None or crypt_hash in (b'*0', b'*1') or not crypt_hash.startswith(b'$y$'):
		debug('yescrypt not supported by this libc, falling back to SHA-512')
		salt = crypt_gen_salt('$6$', 5000)
		crypt_hash = libcrypt.crypt(enc_plaintext, salt)

	if crypt_hash is None:
		raise ValueError('crypt() returned NULL')

	return cast(bytes, crypt_hash).decode('utf-8')
