# Systemd Dependency Removal

Many distros provide `arch-install-scripts`, `pacman` and related tools.
Goal: build and run archinstoo from **any Linux distro** (Alpine, Debian, Fedora, …).
Calls that operate on the **target** system (chroot / `--root=`) are intentional and must stay.
Only **host-side** systemd calls need to be eliminated → Inside chroot is fine.

The idea is to test more host-to-target (h2t) installs without ISOs:
Mainly to see which parts of codebase have either: 

Clean-up issues or Timing issues with weird disk configs

---

## Target-side calls (keep as-is)

| Call | File | Why it's fine |
|------|------|---------------|
| `systemctl --root={target} enable/disable` | `lib/installer.py` | Operates on target root, not the live host |
| `bootctl install` via `arch_chroot` | `lib/installer.py` | Runs inside the chroot |
| Config writes to `self.target / …` | `lib/installer.py` | Pure filesystem writes |
| `enable_linger()` | `lib/installer.py` | Creates files in target FS only |
| `enable_user_service()` | `lib/installer.py` | Creates symlinks in target FS only |
| Unit names in `lib/applications/cat/*` | various | Data only, consumed by the target-side calls above |

---

## Host-side removals — status

### 1. `timedatectl show` — NTP sync polling
- **File:** `lib/installer.py` (`_verify_service_stop`)
- **Status:** ✅ Guarded — skipped when `timedatectl` is not on PATH.
- **Long-term:** Replace with `/proc/net/adjtimex` read or a simple clock sanity check;
  the exact NTP sync state is not required, only a "time looks sane" guard.

### 2. `systemctl show` — host service state polling
- **File:** `lib/installer.py` (`_service_started`, `_service_state`)
- **Callers:** reflector wait, archlinux-keyring-wkd-sync wait
- **Status:** ✅ Guarded — both return early (`'dead'`) when `systemctl` is not on PATH.
- **Long-term:** Replace with filesystem artifact checks:
  - reflector → watch `/var/lib/reflector/mirrorlist` mtime
  - keyring sync → check gnupg trust DB mtime in `/etc/pacman.d/gnupg/`
  - similar pattern to how we bootsrap `pacman` files 

### 3. `systemctl is-active espeakup.service` — accessibility detection
- **File:** `lib/installer.py` (`accessibility_tools_in_use()`)
- **Status:** ✅ Guarded — returns `False` when `systemctl` is not on PATH.
- **Long-term:** Replace with `/proc/*/comm` scan for `espeakup` process.

### 4. `systemd-detect-virt` — VM detection
- **File:** `lib/hardware.py` (`SysInfo.is_vm`)
- **Status:** ✅ Replaced — falls back to DMI vendor string
  (`/sys/class/dmi/id/sys_vendor`) and `/sys/hypervisor/type` when
  `systemd-detect-virt` is not on PATH.

### 5. `arch-chroot -S` — systemd-run dependency
- **File:** `lib/installer.py` (all `arch-chroot` invocations)
- **Status:** ✅ Fixed — `_arch_chroot_cmd` property omits `-S` when `systemd-run`
  is not available. All hardcoded `arch-chroot -S` literals replaced with
  `*self._arch_chroot_cmd`.

### 6. `systemctl --root=` enable/disable on non-systemd hosts
- **File:** `lib/installer.py` (`enable_service`, `disable_service`)
- **Status:** ✅ Fixed — falls back to running `systemctl enable/disable` inside
  the chroot when the host `systemctl` is absent.

### 7. `systemd.journal` — host journal logging
- **File:** `lib/output.py` (`Journald.log`)
- **Status:** ✅ Removed — `Journald` class deleted, call site removed.
  `systemd_python` dep removed from `pyproject.toml`, both `PKGBUILD` files,
  and `nvchecker/nvchecker.toml`.

### 8. `installed_package('systemd')` — host systemd version probe
- **File:** `lib/installer.py` (bootctl version gate)
- **Status:** ✅ Fixed — now runs `bootctl --version` inside the chroot and parses
  the version from its output. No host pacman query. Import removed.

---

## New capabilities (non-Arch host bootstrap)

Added to `lib/utils/env.py`:

| Function | Purpose |
|----------|---------|
| `ensure_pacman_configured()` | Writes a default mirrorlist and fetches `pacman.conf` from upstream when no repos are configured (e.g. Alpine). |
| `ensure_keyring_initialized()` | Downloads `archlinux-keyring`, extracts it, and runs `pacman-key --init --populate` when the keyring is absent. |

Called from `__init__._prepare()` before `pacman -Sy` so that pacman works on any host.

`_deps_available()` in `__init__` short-circuits the bootstrap when `python-pyparted`
is already importable (e.g. Alpine provides `py3-parted` ...).

---

## Other portability fixes

| Fix | File | Detail |
|-----|------|--------|
| `localectl` fallback | `lib/localization/utils.py` | All calls fall back to keymap file scan / vconsole.conf read when `localectl` is absent |
| `timedatectl list-timezones` fallback | `lib/localization/utils.py` | Falls back to `/usr/share/zoneinfo` scan |
| `list_locales()` fallback | `lib/localization/utils.py` | Falls back to `/etc/locale.gen`, then hardcoded defaults when `/usr/share/i18n/SUPPORTED` is absent |
| `_pid_exists` portability | `lib/general.py` | Replaced `ps --no-headers` (procps-specific) with `os.kill(pid, 0)` |
| `crypt.py` musl support | `lib/authentication/crypt.py` | Portable library discovery; correct `crypt_gensalt` symbol check via `lib['name']` (not `hasattr`); SHA-512 fallback when yescrypt is unsupported |

---
