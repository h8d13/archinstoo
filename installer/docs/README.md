# Project Tree
```
./
├── archinstoo/
│   ├── default_profiles/
│   │   ├── desktop
│   │   ├── desktops/
│   │   │   ├── awesome
│   │   │   ├── bspwm
│   │   │   ├── budgie
│   │   │   ├── cinnamon
│   │   │   ├── cosmic
│   │   │   ├── deepin
│   │   │   ├── dms_assets/
│   │   │   │   ├── hyprland/
│   │   │   │   │   ├── dms/
│   │   │   │   │   │   ├── binds.lua
│   │   │   │   │   │   ├── binds-user.lua
│   │   │   │   │   │   ├── colors.lua
│   │   │   │   │   │   ├── cursor.lua
│   │   │   │   │   │   ├── layout.lua
│   │   │   │   │   │   ├── outputs.lua
│   │   │   │   │   │   └── windowrules.lua
│   │   │   │   │   └── hyprland.lua
│   │   │   │   └── niri/
│   │   │   │       ├── dms/
│   │   │   │       │   ├── alttab.kdl
│   │   │   │       │   ├── binds.kdl
│   │   │   │       │   ├── colors.kdl
│   │   │   │       │   ├── cursor.kdl
│   │   │   │       │   ├── layout.kdl
│   │   │   │       │   └── outputs.kdl
│   │   │   │       └── niri.kdl
│   │   │   ├── dms
│   │   │   ├── enlightenment
│   │   │   ├── gnome
│   │   │   ├── hyprland
│   │   │   ├── i3
│   │   │   ├── labwc
│   │   │   ├── lxqt
│   │   │   ├── mate
│   │   │   ├── niri
│   │   │   ├── plasma
│   │   │   ├── qtile
│   │   │   ├── river
│   │   │   ├── sway
│   │   │   ├── xfce4
│   │   │   └── xmonad
│   │   ├── minimal
│   │   ├── server
│   │   ├── servers/
│   │   │   ├── cockpit
│   │   │   ├── docker
│   │   │   ├── httpd
│   │   │   ├── java
│   │   │   ├── lighttpd
│   │   │   ├── mariadb
│   │   │   ├── nginx
│   │   │   ├── postgresql
│   │   │   ├── sshd
│   │   │   ├── tailscale
│   │   │   └── tomcat
│   │   ├── wayland
│   │   └── xorg
│   ├── lib/
│   │   ├── applications/
│   │   │   ├── application_handler
│   │   │   ├── application_menu
│   │   │   └── cat/
│   │   │       ├── audio
│   │   │       ├── bluetooth
│   │   │       ├── devtools
│   │   │       ├── editor
│   │   │       ├── firewall
│   │   │       ├── languages
│   │   │       ├── management
│   │   │       ├── monitor
│   │   │       ├── power_management
│   │   │       ├── print_service
│   │   │       └── security
│   │   ├── args
│   │   ├── authentication/
│   │   │   ├── authentication_menu
│   │   │   ├── password_prompt
│   │   │   ├── shell
│   │   │   └── users_menu
│   │   ├── bootloader/
│   │   │   └── bootloader_menu
│   │   ├── checkpoints
│   │   ├── configuration
│   │   ├── crypt
│   │   ├── disk/
│   │   │   ├── cleanup
│   │   │   ├── conf
│   │   │   ├── device_handler
│   │   │   ├── disk_menu
│   │   │   ├── encryption_menu
│   │   │   ├── fido
│   │   │   ├── filesystem
│   │   │   ├── layouts
│   │   │   ├── luks
│   │   │   ├── lvm
│   │   │   ├── partitioning_menu
│   │   │   ├── selectors
│   │   │   ├── subvolume_menu
│   │   │   └── utils
│   │   ├── exceptions
│   │   ├── general
│   │   ├── global_menu
│   │   ├── grimoire*
│   │   ├── hardware
│   │   ├── installer
│   │   ├── interactions/
│   │   │   ├── general_conf
│   │   │   └── system_conf
│   │   ├── linux_path
│   │   ├── localization/
│   │   │   └── utils
│   │   ├── menu/
│   │   │   ├── abstract_menu
│   │   │   ├── list_manager
│   │   │   ├── locale_menu
│   │   │   └── menu_helper
│   │   ├── models/
│   │   │   ├── application
│   │   │   ├── authentication
│   │   │   ├── bootloader
│   │   │   ├── device
│   │   │   ├── firmware
│   │   │   ├── kernel
│   │   │   ├── locale
│   │   │   ├── mirrors
│   │   │   ├── network
│   │   │   ├── packages
│   │   │   ├── profile
│   │   │   ├── service
│   │   │   ├── users
│   │   │   └── zram
│   │   ├── network/
│   │   │   ├── interfaces
│   │   │   ├── network_handler
│   │   │   └── network_menu
│   │   ├── output
│   │   ├── pacman
│   │   ├── pathnames
│   │   ├── pm/
│   │   │   ├── bootstrap
│   │   │   ├── config
│   │   │   ├── mirrors
│   │   │   └── packages
│   │   ├── profile/
│   │   │   ├── base
│   │   │   ├── driver_select
│   │   │   ├── profile_menu
│   │   │   └── profiles_handler
│   │   ├── tui/
│   │   │   ├── content_editor
│   │   │   ├── curses_menu
│   │   │   ├── help
│   │   │   ├── menu_item
│   │   │   ├── prompts
│   │   │   ├── result
│   │   │   └── types
│   │   └── utils/
│   │       ├── env
│   │       ├── net
│   │       └── unicode
│   ├── __main__
│   ├── schema.jsonc
│   ├── scripts/
│   │   ├── count
│   │   ├── format
│   │   ├── guided
│   │   ├── list
│   │   ├── live
│   │   ├── minimal
│   │   ├── mirror
│   │   ├── packages
│   │   ├── rescue
│   │   ├── _resolve
│   │   └── size
│   └── _version
├── examples/
│   ├── config_custom.json
│   ├── config_sample_full.json
│   ├── custom
│   └── vm_configuration.json
├── PKGBUILD
├── pyproject.toml
└── tests/
    ├── conftest
    ├── data/
    │   └── test_config.json
    ├── test_args
    ├── test_available_packages
    ├── test_bootstrap
    ├── test_configuration_output
    ├── test_deps
    ├── test_env
    ├── test_firmware
    ├── test_locale
    ├── test_menu_item_focus
    ├── test_mirrors
    ├── test_parted_optional
    ├── test_saved_config_resume
    ├── test_schema_drift
    ├── test_script_peek
    └── test_version_stamp

29 directories, 177 files
```
