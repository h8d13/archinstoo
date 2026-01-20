.. _help.issues:

Report Issues & Bugs
====================

Issues and bugs should be reported on the project's Issue Tracker.

General questions, enhancements and security issues can be reported over there too.
For quick issues or if you need help, head over to the Discord server which has a help channel.

Log files
---------

When submitting a help ticket, please include the :code:`/var/log/archinstoo/install.log`.
It can be found both on the live ISO but also in the installed filesystem if the base packages were strapped in.

.. tip::
   | An easy way to submit logs is ``curl -F 'file=@/var/log/archinstoo/install.log' https://0x0.st``.
   | Use caution when submitting other log files, but ``archinstall`` pledges to keep ``install.log`` safe for posting publicly!

There are additional log files under ``/var/log/archinstoo/`` that can be useful:

 - ``/var/log/archinstoo/user_configuration.json`` - Stores most of the guided answers in the installer
 - ``/var/log/archinstoo/user_disk_layouts.json`` - Stores the chosen disks and their layouts
 - ``/var/log/archinstoo/install.log`` - A log file over what steps were taken by archinstall
 - ``/var/log/archinstoo/cmd_history.txt`` - A complete command history, command by command in order
 - ``/var/log/archinstoo/cmd_output.txt`` - A raw output from all the commands that were executed by archinstall

.. warning::

    We only try to guarantee that ``/var/log/archinstoo/install.log`` is free from sensitive information.
    Any other log file should be pasted with **utmost care**!
