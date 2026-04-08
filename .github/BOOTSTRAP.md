# Cross-Distro Host Support

Goal: run `archinstoo` from **any Linux distro** as the host  Alpine, Debian, Fedora, Arch ISO, whatever, a shell and 5 minutes.

The host is treated as a throwaway bootstrap environment, which is a bit unjust as being able to run an app anywhere is important. 
The target is what matters, but how you even run a program, or see its traces, is just as primordial.
Systemd dep removal is a means to that end, not the goal itself.

Calls that operate on the **target** system (chroot / `--root=`) are intentional and must stay.
Only **host-side** tool dependencies need to be eliminated or given fallbacks → inside chroot is always fine.

The idea is to test more host-to-target (h2t) installs without ISOs 
(as ISO-testing seems to be standard, but is bad practice since it's only a tmp envir, with a lot of tools added, easy to lose track of which tool did what, pr discard proper clean-up steps)

Mainly to see which parts of codebase have either: 
Clean-up issues or Timing issues with weird disk configs

The other side is also that sysd is available in the target either-way. 
So was there really any major reason for it to be called on the host (often considered temp, ISO env) system, or for other calls to prompt host at all.
This is obviously not to say systemd bad, just that it should only be used within the target and not on the host.

The rest of this document is how I've found a back-up for each issue:

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

## Host-side removals : status

### 1. `timedatectl show` : NTP sync polling
- **File:** `lib/installer.py` (`_verify_service_stop`)
- **Status:**   Guarded : skipped when `timedatectl` is not on PATH.
- **Long-term:** Replace with `/proc/net/adjtimex` read or a simple clock sanity check;
  the exact NTP sync state is not required, only a "time looks sane" guard.

### 2. `systemctl show` : host service state polling
- **File:** `lib/installer.py` (`_service_started`, `_service_state`)
- **Callers:** reflector wait, archlinux-keyring-wkd-sync wait
- **Status:**   Guarded : both return early (`'dead'`) when `systemctl` is not on PATH.
- **Long-term:** Replace with filesystem artifact checks:
  - reflector → watch `/var/lib/reflector/mirrorlist` mtime
  - keyring sync → check gnupg trust DB mtime in `/etc/pacman.d/gnupg/`
  - similar pattern to how we bootsrap `pacman` files 

### 3. `systemctl is-active espeakup.service` : accessibility detection
- **File:** `lib/installer.py` (`accessibility_tools_in_use()`)
- **Status:**   Guarded : returns `False` when `systemctl` is not on PATH.
- **Long-term:** Replace with `/proc/*/comm` scan for `espeakup` process.

### 4. `systemd-detect-virt` : VM detection
- **File:** `lib/hardware.py` (`SysInfo.is_vm`)
- **Status:**   Replaced : falls back to DMI vendor string
  (`/sys/class/dmi/id/sys_vendor`) and `/sys/hypervisor/type` when
  `systemd-detect-virt` is not on PATH.

### 5. `arch-chroot -S` : systemd-run dependency
- **File:** `lib/installer.py` (all `arch-chroot` invocations)
- **Status:**   Fixed : `_arch_chroot_cmd` property omits `-S` when `systemd-run`
  is not available. All hardcoded `arch-chroot -S` literals replaced with
  `*self._arch_chroot_cmd`  covers `run_command`, `set_user_password`,
  `snapper` config, `grub-install`, and `run_custom_user_commands`.

### 6. `systemctl --root=` enable/disable on non-systemd hosts
- **File:** `lib/installer.py` (`enable_service`, `disable_service`)
- **Status:**   Fixed : falls back to running `systemctl enable/disable` inside
  the chroot when the host `systemctl` is absent.

### 7. `systemd.journal` : host journal logging
- **File:** `lib/output.py` (`Journald.log`)
- **Status:**   Removed : `Journald` class deleted, call site removed.
  `systemd_python` dep removed from `pyproject.toml`, both `PKGBUILD` files,
  and `nvchecker/nvchecker.toml`.

### 8. `installed_package('systemd')` : host systemd version probe
- **File:** `lib/installer.py` (bootctl version gate)
- **Status:** Fixed : now runs `bootctl --version` inside the chroot and parses
  the version from its output. No host pacman query. Import removed.

COMPLETLY STRIPPED. Should not be checked from host

---

## New capabilities (non-Arch host bootstrap)

Added to `lib/pm/bootstrap.py`:

| Function | Purpose |
|----------|---------|
| `keyring_init()` | Scrapes `geo.mirror.pkgbuild.com` for the latest `archlinux-keyring` `.zst`, decompresses via `zstd -d -c` subprocess into a temp `.tar`, extracts with `tarfile`, copies keys to `/usr/share/pacman/keyrings/`, then runs `pacman-key --init --populate archlinux`. No-op if the keyring is already present. |
| `pacman_conf()` | Fetches `pacman.conf` from upstream Arch GitLab and a live mirrorlist from `archlinux.org/mirrors/status/json/` when no repo sections exist in `/etc/pacman.conf`. Removes `DownloadUser` so it works on non-Arch hosts. No-op if repos are already configured. |

Called from `__init__._prepare()` in order  `keyring_init()` first, then `pacman_conf()`  so signature checking works at its upstream default (no `SigLevel = Never` needed).

`_deps_available()` in `__init__` checks if `parted` is already importable and short-circuits the pacman bootstrap entirely  e.g. Alpine ships `py3-parted` so no pacman install step is needed. `_prepare()` also skips the bootstrap on non-Arch hosts for the same reason.

---

## Other portability fixes

### Localization (`lib/localization/utils.py`)

| Function | Fallback chain |
|----------|---------------|
| `list_keyboard_languages()` | `localectl --no-pager list-keymaps` → fetch keymap names from kbd GitHub tree (`api.github.com/repos/legionus/kbd`) |
| `list_x11_keyboard_languages()` | `localectl --no-pager list-x11-keymap-layouts` → fetch layout names from xkeyboard-config GitLab (`base.lst`) |
| `get_kb_layout()` | `localectl --no-pager status` → read `KEYMAP=` from `/etc/vconsole.conf` |
| `set_kb_layout()` | `localectl set-keymap` → `loadkeys` |
| `list_timezones()` | `timedatectl --no-pager list-timezones` → recursive scan of `/usr/share/zoneinfo` (skipping meta-files) |
| `list_locales()` | `/usr/share/i18n/SUPPORTED` → `/etc/locale.gen` → fetch upstream glibc `localedata/SUPPORTED` from GitHub |
| `list_console_fonts()` | Fully rewritten: fetches font names from kbd GitHub tree (`data/consolefonts/`); strips `.psfu.gz`, `.psf.gz`, `.gz`, `.psfu`, `.psf` suffixes; returns `[]` on any network error |

### Other

| Fix | File | Detail |
|-----|------|--------|
| `_pid_exists` portability | `lib/general.py` | Replaced `ps --no-headers` (procps-specific) with `os.kill(pid, 0)` |
| `crypt.py` musl support | `lib/authentication/crypt.py` | Portable library discovery; correct `crypt_gensalt` symbol check via `lib['name']` (not `hasattr`); SHA-512 fallback when yescrypt is unsupported; fixed sentinel check  musl falls through to DES (not `*0`/`*1`) for unknown algorithms, so the fallback now also triggers when the result doesn't start with `$y$` |
| Mirror quality filtering | `lib/pm/mirrors.py` | `get_status_by_region` now filters out mirrors with `score ≥ 2.0` or `delay > 3600 s`, caps results at `TOP_N = 10`, and only prints speed-test progress on first call (cached thereafter). `speed_sort` is always `True` now since results are cached. |

---

Clean up canonical sources:

- Check for copy from ISO option is it safe in case of no-ops (no systemd host to copy from)


