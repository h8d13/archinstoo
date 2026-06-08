# Walkthrough

## Menu items

- `Disk config` & `Authentication` => Assumed to **not be resumed**

Disk is self-explanatory and kinda risky always. *Multi-disk was removed because adding disks later on is trivial*

They let decide where to install to set up `users/groups/elevation/shells` + `stashes`

- `Locales` & `Pacman` & `TZ`/`NTP` & `Hostname`

This tries to follow the ArchWiki as close as possible.

These are main auto configurations that are found on the system or need to be setup. This is usually done through `systemctl` calls or `/etc` 

`terminus-font` is auto-added when requested as a console font through `/etc/vconsole.conf`
A keymap is also set here.

Repos, mirrors, misc options.

- `Bootloader` & `Swap` & `Kernels`/`Headers` & `Firmware`

These are also self-explained. And critical. Can select several kernels.

- `Network`

Options here are also important: Both `NetworkManager`:
	- Default backend `wpa_supplicant` (Others)
	- IWD backend `iwd` managed by NM (Usually for Intel hardware)
	- Copy from ISO (Use current config) minimal `systemd` network features
	- IWD standalone

Usually I pick Copy to ISO from VMs or a desktop (cabled) and other two options for laptops this allows for proper integration to `DE`or`WM`.

- `Applications` & `Profile`

This is all up to user preference, can be multi-selected / some set the global default (like `Editor`) through `/etc/environment`

```
  Bluetooth            
  Audio
  Print service
  Firewall
  Power Management (laptops only)
  Management
  Monitor
  Editor
  Security
  ← Back
```

> Hardware drivers can also be skipped and added to AUR step bellow if needed.

- `Additional packages` & `AUR packages` 

You can also add something like `noto-fonts` variants at this step or anythign you would like in target really.

Also all up to user preference, AUR hidden behind `--advanced` this allows to build DKMS drivers.

**Make sure to toggle `Kernel Headers` when doing so.**

- `Systctl` & `Custom commands`

This is experimental feature which allows me test some additional automation steps.

---

## Working on customizing

Configs and custom profiles references can be found in [`examples/`](https://github.com/h8d13/archinstoo/tree/master/archinstoo/examples)

You can also add them directly in [`default_profiles/`](https://github.com/h8d13/archinstoo/tree/master/archinstoo/archinstoo/default_profiles) following other profiles as example or modify existing ones.

And master [`schema.jsonc`](https://github.com/h8d13/archinstoo/blob/master/archinstoo/archinstoo/schema.jsonc)
