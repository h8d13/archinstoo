# API Reference

How to extend, run, or edit the installer.
Default flow:
[guided.py](https://github.com/h8d13/archinstoo/blob/master/archinstoo/archinstoo/scripts/guided.py).

## Run a script standalone

`python -m archinstoo --script <name>` (or installed `archinstoo --script
<name>`). Dispatch:
[__init__.py](https://github.com/h8d13/archinstoo/blob/master/archinstoo/archinstoo/__init__.py)
`run_as_a_module()` -> `main()` ->
[_run_script](https://github.com/h8d13/archinstoo/blob/master/archinstoo/archinstoo/lib/checkpoints.py),
which just `import`s `archinstoo.scripts.<name>`. Each script
([scripts/](https://github.com/h8d13/archinstoo/blob/master/archinstoo/archinstoo/scripts))
**runs on import** (calls its entry fn at file bottom, e.g. `guided()`), so
importing == running. Default script `guided`.

- `--dry-run`: build + save config, then `SystemExit(0)` (no disk writes).
- `--config <file>`: load saved selections, skip resume prompt.
- Rootless (no root needed): `{'list', 'size', 'mirror', 'count'}` in
  [__init__.py](https://github.com/h8d13/archinstoo/blob/master/archinstoo/archinstoo/__init__.py).
- New script = new file in `scripts/` that defines + calls an entry fn.
  Reuse `get_arch_config_handler()` from
  [args.py](https://github.com/h8d13/archinstoo/blob/master/archinstoo/archinstoo/lib/args.py)
  for config/args.

## Add an application (audio/firewall/... category or `cat/`)

Four edits, model first:

1. [models/application.py](https://github.com/h8d13/archinstoo/blob/master/archinstoo/archinstoo/lib/models/application.py):
   add the `StrEnum` of choices, a `XConfiguration` dataclass with
   `json()`/`parse_arg()`, a `XConfigSerialization` TypedDict, then wire it
   into `ApplicationConfiguration` (new field), `_config_parsers` (the
   dispatch dict), and `ApplicationSerialization`. The in-file comment near
   `parse_arg` documents this.
2. [applications/cat/](https://github.com/h8d13/archinstoo/blob/master/archinstoo/archinstoo/lib/applications/cat)
   new `x.py`: class with `install(self, install_session, x_config)`.
   Package/service lists as `@property`. Use `install_session`
   primitives (below). Pattern:
   [firewall.py](https://github.com/h8d13/archinstoo/blob/master/archinstoo/archinstoo/lib/applications/cat/firewall.py).
3. [application_handler.py](https://github.com/h8d13/archinstoo/blob/master/archinstoo/archinstoo/lib/applications/application_handler.py):
   `install_applications()` add `if app_config.x_config: XApp().install(...)`.
   Ordering matters (apps run before bootloader, after users).
4. [application_menu.py](https://github.com/h8d13/archinstoo/blob/master/archinstoo/archinstoo/lib/applications/application_menu.py):
   add a `MenuItem` + `select_x()` + `_prev_x()` so the user can pick it.

## Add a profile (server or desktop)

No registration. Drop a file in
[default_profiles/servers/](https://github.com/h8d13/archinstoo/blob/master/archinstoo/archinstoo/default_profiles/servers)
or
[desktops/](https://github.com/h8d13/archinstoo/blob/master/archinstoo/archinstoo/default_profiles/desktops);
[profiles_handler.py](https://github.com/h8d13/archinstoo/blob/master/archinstoo/archinstoo/lib/profile/profiles_handler.py)
auto-discovers via `importlib` over the dir.

Subclass `Profile`
([profile/base.py](https://github.com/h8d13/archinstoo/blob/master/archinstoo/archinstoo/lib/profile/base.py)),
set `ProfileType` (`ServerType` / `DesktopEnv` / `WindowMgr`). Contract
(all optional except a type):
- `packages` / `services` (`@property`) -> installed + enabled by the parent
  collector ([server.py](https://github.com/h8d13/archinstoo/blob/master/archinstoo/archinstoo/default_profiles/server.py)).
- `install(install_session)` extra steps (e.g.
  [sshd.py](https://github.com/h8d13/archinstoo/blob/master/archinstoo/archinstoo/default_profiles/servers/sshd.py)
  opens the firewall).
- `post_install(install_session)`, `provision(install_session, users)`,
  `do_on_select()`, `default_greeter_type`, `display_servers()`.

## Add a new install step (outside cat/ and profiles)

The general case: work that is neither a category app nor a profile. Two
decoupled parts.

1. **The worker.** A plain class/module anywhere sensible under `lib/`,
   exposing `install(install_session, <config it needs>)` and using the
   Installer primitives below. Canonical example, user shells:
   [shell.py](https://github.com/h8d13/archinstoo/blob/master/archinstoo/archinstoo/lib/authentication/shell.py)
   `ShellApp.install(install_session, users)` installs non-bash shells then
   `chsh` per user. No `cat/` entry, no menu of its own.
2. **The hook.** Call it from `perform_installation` in
   [guided.py](https://github.com/h8d13/archinstoo/blob/master/archinstoo/archinstoo/scripts/guided.py),
   gated on the config it needs, at the right point in the order (`ShellApp`
   runs right after `create_users`, line ~116). Mirror into
   [live.py](https://github.com/h8d13/archinstoo/blob/master/archinstoo/archinstoo/scripts/live.py)
   if it applies to live mode. Either inline `Worker().install(...)` (the
   ShellApp style) or build a handler once in the entry fn and thread it
   through the signature (the `ProfileHandler`/`ApplicationHandler` style).

Order is load-bearing: place the hook relative to the steps it depends on
(after users, before bootloader, ...). The `Installer` context isn't open
yet in the entry fn, so the hook must live inside `perform_installation`.

## Configure it: menu + config field

A menu entry only **captures + persists** a choice; it runs nothing at
install time. To act on it you still need a step (above) that reads it.

[global_menu.py](https://github.com/h8d13/archinstoo/blob/master/archinstoo/archinstoo/lib/global_menu.py):
add `MenuItem(action=self._select_x, key='x')` + the `_select_x` handler.
`key` must match a field on `ArchConfig`
([args.py](https://github.com/h8d13/archinstoo/blob/master/archinstoo/archinstoo/lib/args.py))
so it round-trips through save/load. Toggle visibility with
`set_enabled()` / `set_mandatory()` (live mode disables several). Config
with no consuming step is a dead option; conversely a step can derive from
existing config and skip the menu entirely (shell is a field on each
`User`, set in the auth menu, never a top-level item).

## Edit an existing install step

Built-in steps are methods on `Installer`
([installer.py](https://github.com/h8d13/archinstoo/blob/master/archinstoo/archinstoo/lib/installer.py))
called in order from `perform_installation`. Edit the method, not the
caller, unless reordering. Primitives reused inside any step / app /
profile:
- `add_additional_packages(pkgs)`, `enable_service(name|list)`.
- `arch_chroot(cmd, run_as=None)`: run argv list in the target.
- `self.target` (`Path` of the new root), `self.handler.config` (full
  `ArchConfig`, e.g. read `app_config.firewall_config`).
- bootloader/keymap/fs: `add_bootloader()`, `set_keyboard()`,
  `minimal_installation()`, `genfstab()`.
