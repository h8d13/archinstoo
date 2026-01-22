# Project Structure
```
.
├── archinstall
│   ├── default_profiles
│   │   ├── custom.py
│   │   ├── desktop.py
│   │   ├── desktops
│   │   │   ├── awesome.py
│   │   │   ├── bspwm.py
│   │   │   ├── budgie.py
│   │   │   ├── cinnamon.py
│   │   │   ├── cosmic.py
│   │   │   ├── cutefish.py
│   │   │   ├── deepin.py
│   │   │   ├── enlightenment.py
│   │   │   ├── gnome.py
│   │   │   ├── hyprland.py
│   │   │   ├── i3.py
│   │   │   ├── labwc.py
│   │   │   ├── lxqt.py
│   │   │   ├── mate.py
│   │   │   ├── niri.py
│   │   │   ├── plasma.py
│   │   │   ├── qtile.py
│   │   │   ├── river.py
│   │   │   ├── sway.py
│   │   │   ├── xfce4.py
│   │   │   └── xmonad.py
│   │   ├── minimal.py
│   │   ├── profile.py
│   │   ├── server.py
│   │   ├── servers
│   │   │   ├── cockpit.py
│   │   │   ├── docker.py
│   │   │   ├── httpd.py
│   │   │   ├── lighttpd.py
│   │   │   ├── mariadb.py
│   │   │   ├── nginx.py
│   │   │   ├── postgresql.py
│   │   │   ├── sshd.py
│   │   │   └── tomcat.py
│   │   ├── wayland.py
│   │   └── xorg.py
│   ├── lib
│   │   ├── applications
│   │   │   ├── application_handler.py
│   │   │   ├── application_menu.py
│   │   │   └── cat
│   │   │       ├── audio.py
│   │   │       ├── bluetooth.py
│   │   │       ├── editor.py
│   │   │       ├── firewall.py
│   │   │       ├── management.py
│   │   │       ├── monitor.py
│   │   │       ├── power_management.py
│   │   │       ├── print_service.py
│   │   │       └── shell.py
│   │   ├── args.py
│   │   ├── authentication
│   │   │   ├── authentication_menu.py
│   │   │   ├── crypt.py
│   │   │   └── users_menu.py
│   │   ├── bootloader
│   │   │   └── bootloader_menu.py
│   │   ├── configuration.py
│   │   ├── disk
│   │   │   ├── conf.py
│   │   │   ├── device_handler.py
│   │   │   ├── disk_menu.py
│   │   │   ├── encryption_menu.py
│   │   │   ├── filesystem.py
│   │   │   ├── luks.py
│   │   │   ├── partitioning_menu.py
│   │   │   ├── subvolume_menu.py
│   │   │   └── utils.py
│   │   ├── exceptions.py
│   │   ├── general.py
│   │   ├── global_menu.py
│   │   ├── hardware.py
│   │   ├── installer.py
│   │   ├── interactions
│   │   │   ├── general_conf.py
│   │   │   └── system_conf.py
│   │   ├── locale
│   │   │   ├── locale_menu.py
│   │   │   └── utils.py
│   │   ├── menu
│   │   │   ├── abstract_menu.py
│   │   │   ├── list_manager.py
│   │   │   └── menu_helper.py
│   │   ├── models
│   │   │   ├── application.py
│   │   │   ├── authentication.py
│   │   │   ├── bootloader.py
│   │   │   ├── device.py
│   │   │   ├── locale.py
│   │   │   ├── mirrors.py
│   │   │   ├── network.py
│   │   │   ├── packages.py
│   │   │   ├── profile.py
│   │   │   └── users.py
│   │   ├── network
│   │   │   ├── network_handler.py
│   │   │   ├── network_menu.py
│   │   │   └── utils.py
│   │   ├── output.py
│   │   ├── pm
│   │   │   ├── config.py
│   │   │   ├── mirrors.py
│   │   │   ├── packages.py
│   │   │   └── pacman.py
│   │   ├── profile
│   │   │   ├── profile_menu.py
│   │   │   └── profiles_handler.py
│   │   ├── translationhandler.py
│   │   ├── tui
│   │   │   ├── curses_menu.py
│   │   │   ├── help.py
│   │   │   ├── menu_item.py
│   │   │   ├── prompts.py
│   │   │   ├── result.py
│   │   │   ├── script_editor.py
│   │   │   └── types.py
│   │   └── utils
│   │       ├── env.py
│   │       └── unicode.py
│   ├── __main__.py
│   └── scripts
│       ├── format.py
│       ├── guided.py
│       ├── list.py
│       ├── minimal.py
│       ├── pre_mount_cli.py
│       ├── rescue.py
│       └── size.py
├── examples
│   ├── config-sample.json
│   └── full_automated_installation.py
├── PKGBUILD
├── pyproject.toml
└── tests
    ├── conftest.py
    ├── data
    │   └── test_config.json
    ├── test_args.py
    └── test_configuration_output.py

24 directories, 121 files
```
