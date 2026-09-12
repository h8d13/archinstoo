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
│   │   │       ├── flatpak
│   │   │       ├── languages
│   │   │       ├── management
│   │   │       ├── media_codecs
│   │   │       ├── monitor
│   │   │       ├── power_management
│   │   │       ├── print_service
│   │   │       ├── security
│   │   │       ├── terminal
│   │   │       └── thunderbolt
│   │   ├── args
│   │   ├── authentication/
│   │   │   ├── accounts
│   │   │   ├── authentication_menu
│   │   │   ├── password_prompt
│   │   │   ├── shell
│   │   │   ├── stash
│   │   │   └── users_menu
│   │   ├── bootloader/
│   │   │   ├── bootloader_menu
│   │   │   ├── install
│   │   │   └── validation
│   │   ├── checkpoints
│   │   ├── configuration
│   │   ├── crypt
│   │   ├── disk/
│   │   │   ├── cleanup
│   │   │   ├── conf
│   │   │   ├── cryptenroll
│   │   │   ├── device_handler
│   │   │   ├── disk_menu
│   │   │   ├── encryption_menu
│   │   │   ├── fido
│   │   │   ├── filesystem
│   │   │   ├── fstab
│   │   │   ├── keyfiles
│   │   │   ├── layouts
│   │   │   ├── luks
│   │   │   ├── lvm
│   │   │   ├── mount
│   │   │   ├── partitioning_menu
│   │   │   ├── selectors
│   │   │   ├── snapshots
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
│   │   ├── kernel/
│   │   │   ├── initramfs
│   │   │   ├── swap
│   │   │   ├── sysctl
│   │   │   └── zram
│   │   ├── linux_path
│   │   ├── localization/
│   │   │   ├── catalog
│   │   │   └── configure
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
│   │   │   ├── service
│   │   │   ├── swap
│   │   │   ├── sysctl
│   │   │   └── users
│   │   ├── network/
│   │   │   ├── interfaces
│   │   │   ├── network_handler
│   │   │   └── network_menu
│   │   ├── output
│   │   ├── pathnames
│   │   ├── pm/
│   │   │   ├── aur
│   │   │   ├── bootstrap
│   │   │   ├── config
│   │   │   ├── groups
│   │   │   ├── mirrors
│   │   │   ├── packages
│   │   │   └── pacman
│   │   ├── profile/
│   │   │   ├── base
│   │   │   ├── config
│   │   │   ├── driver_select
│   │   │   ├── profile_menu
│   │   │   └── profiles_handler
│   │   ├── schema_gen
│   │   ├── schema
│   │   ├── systemd
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

30 directories, 180 files
```
