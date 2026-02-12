# Changelog

Historical changes before I went rogue: [h8d13 commits master](https://github.com/archlinux/archinstall/commits/master/?author=h8d13)
To see general [features](./FEATURES.MD)

## 0.1.1-1
    - Add `smartmontools` to Server profiles (disk health monitoring)
        - This means original profiles list now only contains `xdg-utils | smartmontools` for desktops
        - The rest is all in logic or choices.

Down from original list:

```
	@property
	@override
	def packages(self) -> list[str]:
		return [
			'vi',
			'openssh',
			'wget',
			'iwd',
			'wireless_tools',
			'smartmontools',
			'xdg-utils',
		]
```

## 0.1.1-0

    - Graphics driver improvements
        - Add VM-specific options: `VM (software rendering)` and `VM (virtio-gpu)` allows to pick guest drivers
        - `Mesa (open-source)` auto-detects vulkan-intel or vulkan-radeon based on hardware
        - Plan future implemetation for other drivers
        - Virtual: `vulkan-driver` 
        ALREADY COVERED: `nvidia-utils, vulkan-intel, vulkan-radeon, vulkan-swrast, vulkan-virtio, vulkan-nouveau`
        MISSING: `vulkan-gfxstream, vulkan-dzn, vulkan-asahi, vulkan-freedreno, vulkan-broadcom, vulkan-panfrost, vulkan-powervr`
        - Fix gfx driver installation OoO: now installs BEFORE profiles to satisfy vulkan-driver dependency.
            - This avoid pulling in nvidia-utils on a non-nvidia install because none was installed yet, default or 1st choice
        - Update recommendation text with VM detection hint
    - Pacman config changes
        - Move `parallel_downloads` setting into Pacman config submenu
        - Fix misc options (ILoveCandy) not applied when option doesn't exist in pacman.conf
    - Profile fixes
        - Rename `desktop_base` to `profile_base` (applies to any profile, not just desktop)
        - Move `wireless_tools` to wpa_supplicant backend installation (remove from always installed)
        - Fix profile types: DesktopEnv → WindowMgr
        - Add `preview_text` to WaylandProfile (shows "Type: X (Wayland) or (Xorg)")
    - Bug fixes
        - Fix guided.py advanced options disappearing on install
        - Fix duplicate grub package installation on UEFI systems
        - Fix locale menu

## 0.1.0-1

    - New Security application category
        - AppArmor support with kernel LSM parameter (`lsm=landlock,lockdown,yama,integrity,apparmor,bpf`)
        - Firejail namespace-based sandboxing
        - Bubblewrap low-level sandboxing
        - Multi-select menu allowing any combination of tools
    - Add `fail2ban` to Management tools
        - Auto-enables `fail2ban.service` on install
    - Add `run0` privilege escalation option
        - Systemd-based alternative to sudo/doas
        - Uses polkit, wheel group membership sufficient
        - Update `base-devel-flex` and `grur`
    - Add poweroff option to post-installation menu
        - Useful for VM testing workflows
    - Installer improvements
        - Add `add_kernel_param()` method for applications to set kernel parameters
        - Order:
            - Move user creation before application installation
            - Move application installation before bootloader (kernel params now included in bootloader config)
    - CI/Workflow changes
        - Remove publish workflow
        - Trigger only on pushes
    - Test updates
        - Add security_config to test fixtures
        - Update test assertions for new Security model
    - Work on grimaur linting

## 0.1.0-0

    - ARM (aarch64) support
        - Parse ARM mirror list format (different HTML from x86)
        - Filter out `reflector` on non-x86_64 (not packaged for ARM)
        - Remove `vi` from desktop_base (conflicts with vi compat on ARM)
        - Skip filesystem ops when `wipe=False` on existing partitions and safe copies
        - Graphics driver menu shows only Mesa on ARM
    - Live mode (`--script live`)
        - New `scripts/live.py` for configuring the running system in-place
        - Uses `pacman -S --needed` instead of `pacstrap` when target is `/`
        - Skips `arch-chroot` wrapper when target is `/`
        - Disables disk, bootloader, kernel menu items
    - AUR support
        - Full AUR builder (`grimaur.py`) with temporary non-root user
        - AUR packages menu item (gated behind `--advanced`)
        - Fix `/tmp` writability inside chroot for `makepkg`
        - Out-of-tree DKMS module builds
    - Graphics driver overhaul
        - Replace `VMOpenSource` with `MesaOpenSource` (mesa + libva-mesa-driver)
        - VMs and ARM both default to Mesa group
    - Boot / EFI fixes
        - Move EFI bitness check to `hardware.py`
        - Fix UKI, Grub, EFISTUB installation paths
        - UEFI `/efi` partition maps to `/boot`
        - Add pretty name to `os-release`
        - Named kernel entries (e.g. `linux-zen`)
        - Show `linux-home` flag when mountpoint is `/home`
        - Dependency injection for bootloader skip logic
    - TUI improvements
        - Remove hjkl nav in favor of type-to-search anywhere
        - Fix number key selection
        - Add `greetd` greeter choice (hopefuly cage option soon)
    - Code quality
        - Lazy imports in `__init__.py`
        - Move `ROOTLESS_SCRIPTS` to `__init__.py`, fix `--list` formatting
        - Type checking and mypy fixes
        - Fix resume behavior for saved configurations
    - Docs
        - Add multi-boot guide
        - Add AUR / out-of-tree docs
        - Add philosophy doc
        - Update contributing and headless guides

## 0.0.02-2
    - Add Tailscale and Java (headless JRE) server profiles
    - Add headless server docs with SteamCMD examples
    - Add fallback for common Pacman issues
        - Auto-reset keyring on corrupted packages
        - Auto-reset pacman.conf on dependency failures
    - Fix #3772 try block for mount, add `wipefs` helper
    - Rename `ask` functions to `select` across codebase
    - Remove `advanced_mode` from profile base class
    - Remove all `from __future__ import annotations` lines
    - Change to absolute imports (35 files)
    - Apply ruff lint rules A, C4, FURB, PERF, RET, SIM (-307 lines net)
    - Default root elevation to empty
    - Add `-h2t` flag to DEV script
    - Add `--depth 1` to docs clone
    - Fix honest `type: Any` in output
    - Peek outputs for pacman operations
    - Docs restructure and refresh

## 0.0.02-1
    - Add `/boot` encryption support (#74)
    - Fix /efi mount logic
        - /efi exists → /efi = ESP, /boot = no flags needed
        - /efi absent → /boot = ESP
    - Mark bootable flag only available for BIOS systems
    - Add `argon2id` memory limit, better print
    - Remove `wget` and `openssh` from defaults
    - Auto select Minimal Profile and remove from list
    - Add separator between base actions and terminate actions
    - Fix duplicate entries/filters
    - Clean up comments

## 0.0.02-0
    - Encrypted swap partition support (#4169)
        - Allow swap partitions in the encryption selection menu
        - Add `swap` mapper name (consistent with `root`/`home` naming)
        - Call `swapon` on the LUKS mapper device for encrypted swap
        - Manually add swap fstab entry (genfstab doesn't capture swap mount points)
        - Generate keyfile and crypttab entry for passwordless unlock at boot
    - Fix multi-select ENTER key behavior
        - ENTER now only confirms selection, no longer auto-selects the focused item
        - TAB/SPACE remain the toggle keys for individual items
    - TUI search improvements
        - Auto-activate search when typing any letter (no longer need to press `/` first)
        - Remove `/` requirement from help text
    - Remove `--silent` flag
        - Disk and Authentication config are always required interactively
        - Remove `silent` param from `Pacman`, `ConfigurationHandler.prompt_resume()`
        - Fix custom commands only running with `--advanced` flag
    - Fix final confirmation prompt using recursion
        - Replace recursive `return guided()` / `return format_disk()` with `while` loop
        - Fix `sudo` mention to `elevated privileges` in validation message
    - Console fonts listing
        - Skip `README*` files in `/usr/share/kbd/consolefonts/`
    - Move `generate_password()` from `general.py` to `disk/luks.py`
    - Finish `count` script, move `schema.jsonc` into `archinstall/`
    - Smaller mini config sample
    - Docs: rewrite PHILOSOPHY.md

## 0.0.01-9
    - Add console fonts config
    - Add optional groups per user
    - Move shell config to be per user
    - Various UX changes for resumes/clears
    - Various structure changes
    - Add `count` script to list total pkgs installed by a given config
    - Add custom profiles examples

## 0.0.01-8
    - Start building `env` utils for support to build on alpine
    - Rework `--script list` to show what needs root or not
    - Add actual custom examples #71 
    - Add `count` script that let's you map out how many pkgs would be installed by a profile
    - Add schema.jsonc with all the possible packages installed
    - Add mirrors progress indicator and average bit rate
    - Style changes use `SystemExit` instead of importing sys on every file
    - Add `--clean` args to remove logs too
    - Wrap parted imports in try blocks
    - Update missing packages from plasma profile
    - Add newb docs and refresh more docs
    - Fix missing iwd case for resume
    - Fix disks menu QOL for resume
    - Add `mirror` script
    - Add lazy fallback to unmount
    - Change disks to always show debug

## 0.0.01-7

    - Manual partitioning improvements
        - Add "Create empty layout (wipe all)" option for fresh starts
        - Add "Default layout" option in manual partitioning for brtfs subvolumes
        - Manual partitioning highlighted by default
        - Add udev_sync calls between disk operations for timing issues
        - Remove partprobe (redundant with disk.commit)
        - Add mount_fs to all formatting calls (attempt fixes #4164 vfat mount issues)
        - Always log mount disk operations
    - Init/startup refactor
        - Rework init with cleaner OS imports and lazy args
        - Separate offline check and wire up rc functions properly
        - Move prepare hook, separate helper for ping
        - Bypass unnecessary init steps
    - Config improvements
        - Add config-sample-mini.json (no disk/user data)
        - Add test shortcuts in DEV script (-tf, -tm)
        - Remove duplicate audio_config from test config
    - Fixes
        - Fix shell not being set for user
        - Remove hardcoded sudo mention
        - Grub as default bootloader
    - Chores
        - Update ruff to v0.14.14
        - Code comments and structure cleanup

## 0.0.01-6

    - Mirrors module rework
        - Move mirrors code to `lib/pm/` (package manager)
        - Use class-level cache for `MirrorListHandler` (fetch once, reuse)
        - Swap mirror fetch order: archlinux.org first, archlinux.de fallback
        - Fix "Loading mirror regions..." showing repeatedly
        - Fix "database already registered" error for custom repos
        - Skip duplicate repos when writing to pacman.conf
    - X11 keyboard layout configuration
        - Auto-write `/etc/X11/xorg.conf.d/00-keyboard.conf` for Xorg profiles
        - Use `DisplayServer.X11` check instead of profile type checks
        - Verify layout inside chroot where X11 is installed
        - Strip vconsole suffixes (-latin1, -nodeadkeys, etc.) for X11 format
        - Remove Boot module that had complex systemd-spwn logic for setting this
    - Remove unused `is_xorg_type_profile()` method
    - Use `profile.display_servers()` for graphics driver installation check
    - Network refactor with DI pattern
    - Add accent colors to theme selector
    - Add menu previews
    - Various type hints and cleanup

## 0.0.01-5

    - Dependency Injection refactor (from archinstoo issues #4149)
        - Remove module-level singletons: device_handler, profile_handler, mirror_list_handler, application_handler
        - Consumer classes accept optional handler params with fallback defaults
        - Keep logger and translation_handler as singletons
    - Add `Os` class wrapper for environment variables
        - `Os.get_env()`, `Os.set_env()`, `Os.has_env()`
    - Merge `resumehandler.py` into `ConfigurationHandler`
        - Add `ConfigurationHandler.prompt_resume()` method
        - Fix resume config loading bug (config was captured before resume check)
    - Menu UX improvements
        - Move Disk config and Authentication to top (assumed encryption empty/same for auth)
        - Add `MenuItem.separator()` factory method for visual separators
        - Change "Cancel" to "Back" in sub-menus (ListManager)
        - Move Archinstoo settings to bottom with Install/Abort
    - Update tests and docs for refactors
    - New `logs/` dir for outputs (restore_perms on h2t mode)
    - Move `tui/` into `lib/` for more readable imports / flat lib / honest architecture
        - A lot of UI code is called from lib interactions or similar
        - Having them as siblings when they are interlaced is misleading
    - Separate `env` module in utils for these types of checks
    - Rename `MirrorConfiguration` to `PacmanConfiguration`
        - Add pacman misc options (Color, ILoveCandy, VerbosePkgLists)
        - Rename `mirror_config` field to `pacman_config`
        - Custom repos browsable in Additional packages
        - Apply config on GlobalMenu init for loaded configs
        - Fix repos being added multiple times
    - Rename `.sudo` to `.elev` across codebase
        - Add `User.any_elevated()` static helper
        - Consolidate duplicate elevated user checks
    - Simplify `Password` class
        - Remove unused setter
    - Log to current directory for debugging
    - Light/dark mode theme selector with accent colors
    - Add resizing and various UI fixes
    - Separate scripts that need preparation phase
    - Various test updates for renamed fields

## 0.0.01-4

    - Remove `python-pydantic` dataclasses dependency
        - Use ClassVar abstractions reduce copy/paste
    - Fixes #3717 enable cryptodisk in grub cfg + More UKI
    - Fix #4148 pass script to main and handle non-root commands early
    - Add stash module for git dotfiles
        - Allow multiple stashes per user (clones to `.stash/repo`)
        - Branch parsing with #branch format
    - New settings submenu with color themes
    - Nvidia driver better hints
    - Fix config assertion error on reload
    - Add validators for checkmark and config loading
    - Fix input cursor not being shown and various UI
    - Rework menu sections/orders
    - Simplify bootloader entry naming
        - Remove init_time timestamp mechanism
    - Add examples (custom commands, priv esc, deps)
    - Docs refresh
    - Create `base-devel-flex` pkg for `doas` alternative

## 0.0.01-3

    - Change menu order for mirrors
    - Work on ISOMOD scripts to add pre-caching
        - Profile system/cow space mods
        - Logging etc
    - Work on init scripts debugging
        - Add is_venv check
    - More formatting

## 0.0.01-2

    - Fix vgs not closing properly
    - Fix menu/ Add dynamic resize
    - Chores use walrus op where available
    - Work on DEV / BUILD utils

## 0.0.01-1

    - Change structure to be more readable
        - Editor/PCH goes to top level
        - Rest fo checks are specific to archinstall
        - Seperate into DEV / ONLINE PKGBUILDS
    - Add dev/run helpers bash
    - Remove UV from runners
    - Change more PKGBUILD/workflows for new structure
    - Work on refreshing docs

## 0.0.01-0

    - Change PKGBUILD strucs for proper dependency mngmnt
        - Remove python-cryptography
        - Remove python-textual
        - Add __init__ check of deps
    - Simplify auth config to be inside global config
        - Never output passwords/FDE related
        - Load config but never creds (disk/auth config to do only)
        - Offer choice to delete all of contents post-install
        - Lock root and doas alternative
    - Add resume/abort features with proper deletions of cfg archlinux/archinstall#4035
    - Wayland/x11 major refactor
        - Nvidia fixes
        - Sway, River, Niri fixes
        - Explicit Nogreeter type
    - Custom commands handler
        - Replaced plugins system
    - Explicit --script utils
        - Rescue/Format/Minimal/...
    - More bootloader/UKI fixes
    - More applications menus, less hardcoded defaults
    - Update user facing instructions

    - Remove U2F in favor of configurable privilege escalation tools
    - Remove all backwards compat related code
    - Remove all dead code snippets
