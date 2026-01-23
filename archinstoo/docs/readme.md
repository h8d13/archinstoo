# Project Structure
```
./
├── archinstall/
│   ├── default_profiles/
│   │   ├── custom
│   │   ├── desktop
│   │   ├── desktops/
│   │   │   ├── awesome
│   │   │   ├── bspwm
│   │   │   ├── budgie
│   │   │   ├── cinnamon
│   │   │   ├── cosmic
│   │   │   ├── cutefish
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
│   │   ├── profile
│   │   ├── server
│   │   ├── servers/
│   │   │   ├── cockpit
│   │   │   ├── docker
│   │   │   ├── httpd
│   │   │   ├── lighttpd
│   │   │   ├── mariadb
│   │   │   ├── nginx
│   │   │   ├── postgresql
│   │   │   ├── sshd
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
│   │   │       └── shell
│   │   ├── args
│   │   ├── authentication/
│   │   │   ├── authentication_menu
│   │   │   ├── crypt
│   │   │   └── users_menu
│   │   ├── bootloader/
│   │   │   └── bootloader_menu
│   │   ├── configuration
│   │   ├── disk/
│   │   │   ├── conf
│   │   │   ├── device_handler
│   │   │   ├── disk_menu
│   │   │   ├── encryption_menu
│   │   │   ├── filesystem
│   │   │   ├── luks
│   │   │   ├── partitioning_menu
│   │   │   ├── subvolume_menu
│   │   │   └── utils
│   │   ├── exceptions
│   │   ├── general
│   │   ├── global_menu
│   │   ├── hardware
│   │   ├── installer
│   │   ├── interactions/
│   │   │   ├── general_conf
│   │   │   └── system_conf
│   │   ├── locale/
│   │   │   ├── locale_menu
│   │   │   └── utils
│   │   ├── menu/
│   │   │   ├── abstract_menu
│   │   │   ├── list_manager
│   │   │   └── menu_helper
│   │   ├── models/
│   │   │   ├── application
│   │   │   ├── authentication
│   │   │   ├── bootloader
│   │   │   ├── device
│   │   │   ├── locale
│   │   │   ├── mirrors
│   │   │   ├── network
│   │   │   ├── packages
│   │   │   ├── profile
│   │   │   └── users
│   │   ├── network/
│   │   │   ├── network_handler
│   │   │   ├── network_menu
│   │   │   └── utils
│   │   ├── output
│   │   ├── pacman
│   │   ├── pm/
│   │   │   ├── config
│   │   │   ├── mirrors
│   │   │   └── packages
│   │   ├── profile/
│   │   │   ├── profile_menu
│   │   │   └── profiles_handler
│   │   ├── translationhandler
│   │   ├── tui/
│   │   │   ├── curses_menu
│   │   │   ├── help
│   │   │   ├── menu_item
│   │   │   ├── prompts
│   │   │   ├── result
│   │   │   ├── script_editor
│   │   │   └── types
│   │   └── utils/
│   │       ├── env
│   │       ├── net
│   │       └── unicode
│   ├── __main__
│   └── scripts/
│       ├── format
│       ├── guided
│       ├── list
│       ├── minimal
│       ├── pre_mount_cli
│       ├── rescue
│       └── size
├── examples/
│   ├── config-sample.json
│   └── full_automated_installation
├── PKGBUILD
├── pyproject.toml
└── tests/
    ├── conftest
    ├── data/
    │   └── test_config.json
    ├── test_args
    └── test_configuration_output

24 directories, 122 files
```
