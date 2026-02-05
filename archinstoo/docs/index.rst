archinstoo
==========

SYNOPSIS
--------

**archinstoo** [OPTIONS]

DESCRIPTION
-----------

archinstoo is a guided installer for Arch Linux. It provides a TUI-based
menu system for configuring and installing Arch Linux systems.

OPTIONS
-------

--config PATH
    Path to a local JSON configuration file

--config-url URL
    URL to a remote JSON configuration file

--script NAME
    Script to run (default: guided). Use ``--script list`` to see available scripts.

--dry-run
    Generate config and exit without installing

--mountpoint PATH
    Alternate mount point (default: /mnt)

--skip-ntp
    Skip NTP time sync check

--skip-wkd
    Skip archlinux-keyring WKD sync

--skip-boot
    Skip bootloader installation

--offline
    Disable online package search

--advanced
    Enable advanced menu options

--debug
    Enable debug logging

--clean
    Clean logs/ after run

-h, --help
    Show help message

FILES
-----

logs/install.log
    Main installation log

logs/user_configuration.json
    Saved configuration

logs/cmd_history.txt
    Command history

logs/cmd_output.txt
    Raw command output

EXAMPLES
--------

Run the guided installer::

    archinstoo

Use a saved configuration::

    archinstoo --config /path/to/config.json

Dry run to generate config::

    archinstoo --dry-run

Run on a live ARM system::

    archinstoo --script live

SEE ALSO
--------

Project: https://github.com/h8d13/archinstoo
