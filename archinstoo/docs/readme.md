# Project Structure
```
.
├── archinstall
│   ├── applications
│   │   ├── audio.py
│   │   ├── bluetooth.py
│   │   ├── editor.py
│   │   ├── firewall.py
│   │   ├── management.py
│   │   ├── monitor.py
│   │   ├── power_management.py
│   │   └── print_service.py
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
│   │   │   └── application_menu.py
│   │   ├── args.py
│   │   ├── authentication
│   │   │   └── authentication_menu.py
│   │   ├── bootloader
│   │   │   └── bootloader_menu.py
│   │   ├── boot.py
│   │   ├── configuration.py
│   │   ├── crypt.py
│   │   ├── disk
│   │   │   ├── device_handler.py
│   │   │   ├── disk_menu.py
│   │   │   ├── encryption_menu.py
│   │   │   ├── filesystem.py
│   │   │   ├── partitioning_menu.py
│   │   │   ├── subvolume_menu.py
│   │   │   └── utils.py
│   │   ├── exceptions.py
│   │   ├── general.py
│   │   ├── global_menu.py
│   │   ├── hardware.py
│   │   ├── installer.py
│   │   ├── interactions
│   │   │   ├── disk_conf.py
│   │   │   ├── general_conf.py
│   │   │   ├── manage_users_conf.py
│   │   │   ├── network_menu.py
│   │   │   └── system_conf.py
│   │   ├── locale
│   │   │   ├── locale_menu.py
│   │   │   └── utils.py
│   │   ├── luks.py
│   │   ├── menu
│   │   │   ├── abstract_menu.py
│   │   │   ├── list_manager.py
│   │   │   └── menu_helper.py
│   │   ├── mirrors.py
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
│   │   ├── networking.py
│   │   ├── output.py
│   │   ├── packages
│   │   │   └── packages.py
│   │   ├── pacman
│   │   │   └── config.py
│   │   ├── profile
│   │   │   ├── profile_menu.py
│   │   │   └── profiles_handler.py
│   │   ├── resumehandler.py
│   │   ├── translationhandler.py
│   │   └── utils
│   │       ├── unicode.py
│   │       └── util.py
│   ├── __main__.py
│   ├── scripts
│   │   ├── format.py
│   │   ├── guided.py
│   │   ├── list.py
│   │   ├── minimal.py
│   │   └── rescue.py
│   └── tui
│       ├── curses_menu.py
│       ├── help.py
│       ├── menu_item.py
│       ├── result.py
│       ├── script_editor.py
│       ├── types.py
│       └── ui
│           └── result.py
├── examples
│   ├── config-sample.json
│   ├── disk_layouts-sample.json
│   └── full_automated_installation.py
├── PKGBUILD
├── pyproject.toml
├── renovate.json
├── schema.json
└── tests
    ├── conftest.py
    ├── data
    │   └── test_config.json
    ├── test_args.py
    └── test_configuration_output.py

25 directories, 121 files
```
