.. _guided:

Guided installation
===================

Archinstall ships with a pre-programmed `Guided Installer`_ guiding you through the mandatory steps as well as some optional configurations that can be done.

.. note::

   Other pre-programmed scripts can be invoked by executing :code:`archinstall --script <script>` *(without .py)*. To see a complete list of scripts, run :code:`archinstall --script list` or check the source code `scripts`_ directory.

.. note::

   It's recommended to run ``archinstall`` from the official Arch Linux ISO.


.. warning::
    The installer will not configure WiFi before the installation begins. You need to read up on `Arch Linux networking <https://wiki.archlinux.org/index.php/Network_configuration>`_ before you continue.

CLI Arguments
-------------

The following command-line arguments are available:

.. list-table:: CLI Arguments
   :widths: 25 50 10
   :header-rows: 1

   * - Argument
     - Description
     - Default
   * - ``--config``
     - Path to a local JSON configuration file
     - None
   * - ``--config-url``
     - URL to a remote JSON configuration file
     - None
   * - ``--silent``
     - Disables all prompts (requires config)
     - false
   * - ``--dry-run``
     - Generate config and exit without installing
     - false
   * - ``--script``
     - Script to run for installation
     - guided
   * - ``--mountpoint``
     - Alternate mount point for installation
     - /mnt
   * - ``--skip-ntp``
     - Disable NTP checks during installation
     - false
   * - ``--skip-wkd``
     - Skip archlinux keyring WKD sync check
     - false
   * - ``--skip-boot``
     - Skip bootloader installation
     - false
   * - ``--debug``
     - Enable debug output in logs
     - false
   * - ``--offline``
     - Disable online services (package search, keyring update)
     - false
   * - ``--no-pkg-lookups``
     - Disable package validation before installation
     - false
   * - ``--advanced``
     - Enable advanced options in menus
     - false

Running the guided installation
-------------------------------

To start the installer, run the following in the latest Arch Linux ISO:

.. code-block:: sh

    archinstall

Since the `Guided Installer`_ is the default script, this is the equivalent of running :code:`archinstall guided`


The guided installation also supports installing with pre-configured answers to all the guided steps. This can be a quick and convenient way to re-run one or several installations.

``--config``
------------

This parameter takes a local :code:`.json` file as argument and contains the overall configuration and menu answers for the guided installer.

``--config-url``
----------------

This parameter takes a remote :code:`.json` file as argument and contains the overall configuration and menu answers for the guided installer.

.. note::

   You can always get the latest options for this file with ``archinstall --dry-run``, this executes the guided installer in a safe mode where no permanent actions will be taken on your system but simulate a run and save the configuration to disk.

Example usage
^^^^^^^^^^^^^

.. code-block:: sh

    archinstall --config config.json

.. code-block:: sh

    archinstall --config-url https://domain.lan/config.json

The contents of :code:`https://domain.lan/config.json`:

.. code-block:: json

   {
     "archinstall-language": "English",
     "locale_config": {
       "kb_layout": "us",
       "sys_enc": "UTF-8",
       "sys_lang": "en_US"
     },
     "mirror_config": {
       "mirror_regions": {
         "Australia": [
           "http://archlinux.mirror.digitalpacific.com.au/$repo/os/$arch"
         ]
       }
     },
     "bootloader_config": {
       "bootloader": "Systemd-boot",
       "uki": false,
       "removable": false
     },
     "disk_config": {
       "config_type": "default_layout",
       "device_modifications": [
         {
           "device": "/dev/sda",
           "partitions": [
             {
               "btrfs": [],
               "flags": ["boot"],
               "fs_type": "fat32",
               "size": {
                 "sector_size": null,
                 "unit": "MiB",
                 "value": 512
               },
               "mount_options": [],
               "mountpoint": "/boot",
               "start": {
                 "sector_size": null,
                 "unit": "MiB",
                 "value": 1
               },
               "status": "create",
               "type": "primary"
             },
             {
               "btrfs": [],
               "flags": [],
               "fs_type": "ext4",
               "size": {
                 "sector_size": null,
                 "unit": "Percent",
                 "value": 100
               },
               "mount_options": [],
               "mountpoint": "/",
               "start": {
                 "sector_size": null,
                 "unit": "MiB",
                 "value": 513
               },
               "status": "create",
               "type": "primary"
             }
           ],
           "wipe": true
         }
       ]
     },
     "swap": true,
     "kernels": ["linux"],
     "kernel_headers": false,
     "hostname": "archlinux",
     "auth_config": {
       "lock_root_account": false,
       "privilege_escalation": "sudo"
     },
     "app_config": {
       "audio_config": {
         "audio": "pipewire"
       }
     },
     "network_config": {},
     "parallel_downloads": 0,
     "timezone": "UTC",
     "ntp": true,
     "packages": [],
     "services": [],
     "custom_commands": []
   }

``--config`` options
^^^^^^^^^^^^^^^^^^^^

.. warning::

   All key and value entries must conform to the JSON standard. Below is human readable examples with links, effectively breaking the syntax. Adapt the descriptions below to suit your needs and the JSON format.

.. note::

   Scroll to the right in the table to see required options.

.. csv-table:: JSON options
   :file: ../cli_parameters/config/config_options.csv
   :widths: 15, 40, 40, 5
   :escape: !
   :header-rows: 1

.. I'd like to keep this note, as this is the intended behavior of archinstall.
.. note::

   If no entries are found in ``disk_config``, archinstall guided installation will use whatever is mounted currently under ``/mnt/archinstall`` without performing any disk operations.

Authentication Configuration
----------------------------

The ``auth_config`` section handles user authentication setup.

.. warning::

   For security reasons, passwords and user credentials are **never stored** in configuration files.
   Only ``lock_root_account`` and ``privilege_escalation`` are saved. You will always be prompted
   for passwords during installation.

.. code-block:: json

    {
        "auth_config": {
            "lock_root_account": true,
            "privilege_escalation": "sudo"
        }
    }

.. list-table:: ``auth_config`` options (stored in config)
   :widths: 25 25 50
   :header-rows: 1

   * - Key
     - Values
     - Description
   * - ``lock_root_account``
     - ``true``/``false``
     - Whether to lock the root account (recommended if users have sudo)
   * - ``privilege_escalation``
     - ``sudo``/``doas``
     - Which privilege escalation tool to install

.. note::

   At least one of a root password or a user with sudo privileges must be configured during installation.

Application Configuration
-------------------------

The ``app_config`` section configures optional system applications:

.. code-block:: json

    {
        "app_config": {
            "audio_config": {"audio": "pipewire"},
            "bluetooth_config": {"enabled": true},
            "power_management_config": {"power_management": "power-profiles-daemon"},
            "print_service_config": {"enabled": false},
            "firewall_config": {"firewall": "ufw"},
            "management_config": {"tools": ["git", "base-devel"]},
            "monitor_config": {"monitor": "htop"},
            "editor_config": {"editor": "vim"}
        }
    }

.. list-table:: ``app_config`` sub-options
   :widths: 30 40 30
   :header-rows: 1

   * - Key
     - Values
     - Description
   * - ``audio_config.audio``
     - ``pipewire``, ``pulseaudio``, ``No audio server``
     - Audio server to install
   * - ``bluetooth_config.enabled``
     - ``true``/``false``
     - Enable bluetooth support
   * - ``power_management_config.power_management``
     - ``power-profiles-daemon``, ``tuned``
     - Power management daemon
   * - ``print_service_config.enabled``
     - ``true``/``false``
     - Enable CUPS print service
   * - ``firewall_config.firewall``
     - ``ufw``, ``firewalld``
     - Firewall to install
   * - ``management_config.tools``
     - list of: ``git``, ``base-devel``, ``man-db``, ``pacman-contrib``, ``reflector``
     - System management tools
   * - ``monitor_config.monitor``
     - ``htop``, ``btop``, ``bottom``
     - System monitor tool
   * - ``editor_config.editor``
     - ``nano``, ``micro``, ``vi``, ``vim``, ``neovim``, ``emacs``
     - Default text editor

.. _scripts: ../archinstall/scripts
.. _Guided Installer: ../archinstall/scripts/guided.py
