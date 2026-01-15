# Changelog

Historical changes before I went rogue: [h8d13 commits master](https://github.com/archlinux/archinstall/commits/master/?author=h8d13)

> Aims to simplify reading/maintaining the codebase while keeping MORE options available.

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
