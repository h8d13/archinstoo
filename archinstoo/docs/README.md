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
│   │   │       ├── editor
│   │   │       ├── firewall
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
│   │   ├── grimaur*
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
│   │   │   ├── locale
│   │   │   ├── mirrors
│   │   │   ├── network
│   │   │   ├── packages
│   │   │   ├── profile
│   │   │   ├── service
│   │   │   └── users
│   │   ├── network/
│   │   │   ├── interfaces
│   │   │   ├── network_handler
│   │   │   └── network_menu
│   │   ├── output
│   │   ├── pacman
│   │   ├── pathnames
│   │   ├── pm/
│   │   │   ├── config
│   │   │   ├── mirrors
│   │   │   └── packages
│   │   ├── profile/
│   │   │   ├── base
│   │   │   ├── driver_select
│   │   │   ├── profile_menu
│   │   │   └── profiles_handler
│   │   ├── translationhandler
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
│   └── scripts/
│       ├── count
│       ├── format
│       ├── guided
│       ├── list
│       ├── live
│       ├── minimal
│       ├── mirror
│       ├── packages
│       ├── rescue
│       ├── _resolve
│       └── size
├── examples/
│   ├── config-custom.json
│   ├── config-sample-full.json
│   └── custom
├── PKGBUILD
├── pyproject.toml
└── tests/
    ├── conftest
    ├── data/
    │   └── test_config.json
    ├── test_args
    ├── test_configuration_output
    └── test_mirrors

24 directories, 142 files
```
