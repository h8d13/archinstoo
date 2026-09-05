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
│   │   │   │       │   ├── input.kdl
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
│   │   │   ├── noctalia_assets/
│   │   │   │   ├── hyprland/
│   │   │   │   │   └── hyprland.lua
│   │   │   │   ├── labwc/
│   │   │   │   │   ├── autostart
│   │   │   │   │   └── rc.xml
│   │   │   │   ├── niri/
│   │   │   │   │   └── config.kdl
│   │   │   │   └── sway/
│   │   │   │       └── config
│   │   │   ├── noctalia
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
│   │   │       ├── cpu_scheduler
│   │   │       ├── devtools
│   │   │       ├── editor
│   │   │       ├── firewall
│   │   │       ├── languages
│   │   │       ├── management
│   │   │       ├── monitor
│   │   │       ├── power_management
│   │   │       ├── print_service
│   │   │       ├── security
│   │   │       └── terminal
│   │   ├── args
│   │   ├── authentication/
│   │   │   ├── authentication_menu
│   │   │   ├── password_prompt
│   │   │   ├── shell
│   │   │   └── users_menu
│   │   ├── bootloader/
│   │   │   ├── bootloader_menu
│   │   │   └── validation
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
│   │   │   ├── swap
│   │   │   └── users
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
│   │   │   ├── groups
│   │   │   ├── mirrors
│   │   │   └── packages
│   │   ├── profile/
│   │   │   ├── base
│   │   │   ├── driver_select
│   │   │   ├── profile_menu
│   │   │   └── profiles_handler
│   │   ├── schema_gen
│   │   ├── schema
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
│   ├── schema.toml
│   ├── scripts/
│   │   ├── count
│   │   ├── format
│   │   ├── guided
│   │   ├── list
│   │   ├── live
│   │   ├── minimal
│   │   ├── mirror
│   │   ├── packages
│   │   ├── passwd
│   │   ├── rescue
│   │   ├── _resolve
│   │   ├── schema
│   │   └── size
│   └── _version
├── examples/
│   ├── config_custom.json
│   ├── config_sample_full.json
│   ├── custom
│   ├── vm_configuration.json
│   └── vm_unattended.json
├── PKGBUILD
├── pyproject.toml
└── stubs/
    └── parted/
        └── __init__i

34 directories, 177 files
```
