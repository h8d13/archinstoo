# Changelog

Historical changes before I went rogue: [h8d13 commits master](https://github.com/archlinux/archinstall/commits/master/?author=h8d13)

## 0.0.01

    - Change PKGBUILD strucs for proper dependency mngmnt
        - Remove python-cryptography
        - Add __init__ check of deps
    - Simplify creds file to be inside config
        - Never output passwords/FDE related
        - Offer choice to delete all of contents post-install
    - Add resume/abort features with proper deletions of cfg
    - Wayland/x11 major refactor
        - Nvidia fixes
        - Sway, River, Niri fixes
        - Explicit nogreeter type
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
