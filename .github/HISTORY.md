# Changelog

Historical changes before I went rogue: [h8d13 commits master](https://github.com/archlinux/archinstall/commits/master/?author=h8d13)

> Aims to simplify reading/maintaining the codebase while keeping MORE options available, with LESS dependencies/flags BUT more control especially to create media, modify inner workings, without headaches.

## 0.0.01-5
    
    - New `logs/` dir for outputs restored on h2t mode
    - Move `tui/` into `lib/` for more readable imports / flat lib / honest architecture
        - A lot of UI code is called from lib interactions or similar
        - Having them as syblings when they are interlaced is misleading
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
    - Add resume/abort features with proper deletions of cfg
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
