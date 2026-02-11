# Preview

```
Ctrl+C to clear, TAB to select multiple, Ctrl+H for full help - Guided mode

Archinstoo settings    +   ┌─ Info ──────────────────────────────────────────────────────────────────────────────────┐
  ───────────────────      │ Language: English (100%)                                                                │
  Disk config              │ Theme: Dark / Blue                                                                      │
  Authentication           │                                                                                         │
  ───────────────────      │                                                                                         │
  Locales                + │                                                                                         │
  Pacman config            │                                                                                         │
  Bootloader             + │                                                                                         │
  Swap                   + │                                                                                         │
  Kernels                + │                                                                                         │
  Profile                + │                                                                                         │
  Hostname               + │                                                                                         │
  Applications             │                                                                                         │
  Network config           │                                                                                         │
  Timezone                 │                                                                                         │
  Automatic time sync    + │                                                                                         │
  Additional packages      │                                                                                         │
  AUR packages             │                                                                                         │
  Custom commands        + │                                                                                         │
  ───────────────────      │                                                                                         │
  Install                  │                                                                                         │
  Abort					   │																						 │ 
                           └─────────────────────────────────────────────────────────────────────────────────────────┘
```


1. `Disk config` & `Authentication` => Assumed to **not be resumed**

Disk is self-explanatory and kinda risky always.

They let decide where to install to set up `users/groups/elevation/shells` + `stashes`

2. `Locales` & `Pacman` & `TZ`/`NTP` & `Hostname`

These are mainly configurations that are found on the system or need to be setup.
This is usually done through `systemctl` calls or `/etc` 

This tries to follow the ArchWiki as close as possible.

`terminus-font` is auto-added when requested as a console font through `/etc/vconsole.conf`
A keymap is also set here.

Repos, mirrors, misc options.

3. `Bootloader` & `Swap` & `Kernels`/`Headers`

These are also self-explained. And critical. Can select several kernels.

4. `Network`

Options here are also important: Both `NetworkManager`:
	- Default backend `wpa_supplicant` (Others)
	- IWD backend `iwd` managed by NM (Usually for Intel hardware)
	- Copy from ISO (Use current config) minimal `systemd` network features

Usually I pick Copy to ISO from VMs or a desktop (cabled) and other two options for laptops this allows for proper integration to `DE`or`WM`.

5. `Applications` & `Profile`

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

6. `Additional packages` & `AUR packages` 

Also all up to user preference, AUR hidden behind `--advanced` this allows to build DKMS drivers.

Make sure to toggle `Kernel Headers` when doing so.

You can also add something like `noto-fonts` variants at this step.

7. `Custom commands`

This is experimental feature which allows me test some additional automation steps.

---
