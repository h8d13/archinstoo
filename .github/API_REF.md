# API Reference

How to extend, run, or edit the installer. Default flow:
[guided.py](https://github.com/h8d13/archinstoo/blob/master/installer/archinstoo/scripts/guided.py):
`guided()` -> `resolve_config` (menu/save/confirm, or `--silent`) ->
`FilesystemHandler` (partition/format, before anything is mounted) ->
`perform_installation` (`with Installer(...)`, steps in order).

## Run a script standalone

`python -m archinstoo --script <name>` (or installed `archinstoo --script
<name>`). `--script list` prints what is available. `guided` is
`DEFAULT_SCRIPT` in
[args.py](https://github.com/h8d13/archinstoo/blob/master/installer/archinstoo/lib/args.py).

Dispatch:
[`__init__.py`](https://github.com/h8d13/archinstoo/blob/master/installer/archinstoo/__init__.py)
`run_as_a_module()` -> `_prepare()` (deps bootstrap, python re-exec) ->
`main()` (root check, host `pacman.conf` guard) ->
[`_run_script`](https://github.com/h8d13/archinstoo/blob/master/installer/archinstoo/lib/checkpoints.py),
which just `import`s `archinstoo.scripts.<name>`. Rootless scripts skip
`_prepare()` and `main()`: `run_as_a_module()` calls `_run_script` directly.

Each script
([scripts/](https://github.com/h8d13/archinstoo/blob/master/installer/archinstoo/scripts))
**runs on import** (calls its entry fn at file bottom, e.g. `guided()`), so
importing == running. Files starting with `_` are helpers shared between
scripts, not scripts (`_resolve.py`).

- `--dry-run`: build + save config, then `SystemExit(0)`.
- `--config <file>` / `--config-url <url>`: load saved selections, skip
  resume prompt.
- `--silent`: config is the whole input, no menu, no confirm. The script's
  `_validate_silent` fails loud on what the menu would have refused.
- Only `--script` picks the code path. `ArchConfig.script` in the saved
  JSON is a label so a resume knows what produced it (`get_script()`).
- Rootless (no root needed): `ROOTLESS_SCRIPTS` in
  [`__init__.py`](https://github.com/h8d13/archinstoo/blob/master/installer/archinstoo/__init__.py)
  = `list`, `size`, `mirror`, `count`, `schema`. `NO_DISK_SCRIPTS`
  (`live`, `packages`) skip the disk deps and are refused on a foreign
  host: their target is `/`.
- New script = new file in `scripts/` that defines + calls an entry fn.
  Reuse `get_arch_config_handler()` from
  [args.py](https://github.com/h8d13/archinstoo/blob/master/installer/archinstoo/lib/args.py)
  for config/args and `resolve_config(handler, show_menu)` from
  [configuration.py](https://github.com/h8d13/archinstoo/blob/master/installer/archinstoo/lib/configuration.py)
  for the menu/save/confirm loop; `show_menu` is where a script
  `set_enabled`/`set_mandatory`s the `GlobalMenu` for its mode (live,
  packages, format all do this).

## Add an application (audio/firewall/... category or `cat/`)

Worked example: `media_codecs`, a yes/no that installs a fixed set. Follow
it file by file; a single-pick or multi-select category swaps the `enabled`
flag for an enum, the way `firewall`/`management` do.

1. [models/application.py](https://github.com/h8d13/archinstoo/blob/master/installer/archinstoo/lib/models/application.py):
   `MediaCodecsConfigSerialization` (TypedDict, the JSON shape),
   `MediaCodecsConfiguration` (a `_Category` dataclass with its one field:
   an enum, a bool, or a list of enums; `json()`/`parse_arg()` come from the
   base), then the field in `ApplicationSerialization` and
   `ApplicationConfiguration`. A choice category adds its `StrEnum` first.
2. [applications/cat/media_codecs.py](https://github.com/h8d13/archinstoo/blob/master/installer/archinstoo/lib/applications/cat/media_codecs.py):
   `packages` (and `services`) as `@property` literal lists, then
   `install(self, install_session, ...)` using the Installer primitives
   (below).
3. [application_handler.py](https://github.com/h8d13/archinstoo/blob/master/installer/archinstoo/lib/applications/application_handler.py):
   `if app_config.media_codecs_config and ...enabled: MediaCodecsApp().install(...)`.
   Order is install order (apps run before bootloader, after users).
4. [application_menu.py](https://github.com/h8d13/archinstoo/blob/master/installer/archinstoo/lib/applications/application_menu.py):
   a `MenuItem` with `key='media_codecs_config'`, its `_prev_media_codecs`
   and `select_media_codecs`. Flags reuse `_select_enabled` / `_enabled_text`.
   The global menu's Applications preview reads these previews, nothing to
   add there.
5. [schema_gen.py](https://github.com/h8d13/archinstoo/blob/master/installer/archinstoo/lib/schema_gen.py):
   one `Section` in install order, with `pick=('media_codecs_config', 'enabled')`,
   the key path the choice lives at under `app_config`. The pick is what
   `--script count`/`size` walk, so `_resolve.py` needs no edit. Then:

   ```shell
   python -m archinstoo --script schema   # regenerates schema.toml
   ./nvchecker/NVGEN gen                  # tracks the new packages
   ```

`tests/test_schema.py` fails until 5 is done: every `_config_parsers` key
needs a section with a pick, every pick path has to exist in the
serialization, and the committed `schema.toml`/`nvchecker.toml` must match.
Add the category to `examples/config_sample_full.json` so `--config` users
see it.

## Add a profile (server or desktop)

No registration. Drop a file in
[default_profiles/servers/](https://github.com/h8d13/archinstoo/blob/master/installer/archinstoo/default_profiles/servers)
or
[desktops/](https://github.com/h8d13/archinstoo/blob/master/installer/archinstoo/default_profiles/desktops);
[profiles_handler.py](https://github.com/h8d13/archinstoo/blob/master/installer/archinstoo/lib/profile/profiles_handler.py)
auto-discovers via `importlib` over the dir.

Subclass `Profile`
([profile/base.py](https://github.com/h8d13/archinstoo/blob/master/installer/archinstoo/lib/profile/base.py)),
set `ProfileType` (`ServerType` / `DesktopEnv` / `WindowMgr`). Contract
(all optional except a type):

- `packages` / `services` (`@property`) -> installed + enabled by the parent
  collector ([server.py](https://github.com/h8d13/archinstoo/blob/master/installer/archinstoo/default_profiles/server.py)).
- `install(install_session)`: extra install-time steps (e.g.
  [sshd.py](https://github.com/h8d13/archinstoo/blob/master/installer/archinstoo/default_profiles/servers/sshd.py)
  opens the firewall). Runs inside `install_profile_config`, before
  greeter setup; every flow.
- `post_install(install_session)`: system-level finalize after packages
  land, no user context (e.g. mariadb runs `mariadb-install-db`). Runs
  after `install_profile_config` in guided/live/packages; not minimal.
- `provision(install_session, users)`: per-user wiring that needs the user
  list (e.g. docker/wayland add each user to a group,
  `add_to_seat_group`). Runs right after `post_install` in
  guided/live/packages. Guided uses the configured users; live falls back
  to, and packages always uses, the sudo/doas invoking user
  (`invoking_user()` in models/users.py: running-system flows).
- `do_on_select()`: menu-time hook run when the profile is picked.
- `default_greeter_type` / `display_servers()`: graphical metadata (greeter
  default, Xorg/Wayland advertised).

## Add a new install step (outside cat/ and profiles)

The general case: work that is neither a category app nor a profile. Two
decoupled parts.

1. **The worker.** A plain class/module anywhere sensible under `lib/`,
   exposing `install(install_session, <config it needs>)` and using the
   Installer primitives below. Canonical example, user shells:
   [shell.py](https://github.com/h8d13/archinstoo/blob/master/installer/archinstoo/lib/authentication/shell.py)
   `ShellApp.install(install_session, users)` installs non-bash shells then
   `chsh` per user. No `cat/` entry, no menu of its own.
2. **The hook.** Call it from `perform_installation` in
   [guided.py](https://github.com/h8d13/archinstoo/blob/master/installer/archinstoo/scripts/guided.py),
   gated on the config it needs, at the right point in the order (`ShellApp`
   runs right after `create_users`). Mirror into
   [live.py](https://github.com/h8d13/archinstoo/blob/master/installer/archinstoo/scripts/live.py)
   if it applies to live mode, and
   [packages.py](https://github.com/h8d13/archinstoo/blob/master/installer/archinstoo/scripts/packages.py)
   if it concerns profiles/apps/packages/services. Each script holds
   its own copy of the order, there is no shared list. Either inline
   `Worker().install(...)` (the ShellApp style) or build a handler once in
   the entry fn and thread it through the signature (the
   `ProfileHandler`/`ApplicationHandler` style).

Order of Operations: place the hook relative to the steps it depends on
(after users, before bootloader, ...). The `Installer` context isn't open
yet in the entry fn, so the hook must live inside `perform_installation`.
All steps that rely on a previous step must be thought of that way for exec flow...

## Configure it: menu + config field

A menu entry only **captures + persists** a choice; it runs nothing at
install time. To act on it you still need a step (above) that reads it.

[global_menu.py](https://github.com/h8d13/archinstoo/blob/master/installer/archinstoo/lib/global_menu.py):
add `MenuItem(action=self._select_x, key='x')` + the `_select_x` handler.
`key` must match a field on `ArchConfig`
([args.py](https://github.com/h8d13/archinstoo/blob/master/installer/archinstoo/lib/args.py))
so it round-trips through save/load. Toggle visibility with
`set_enabled()` / `set_mandatory()` (live mode disables several). Config
with no consuming step is a dead option; conversely a step can derive from
existing config and skip the menu entirely (shell is a field on each
`User`, set in the auth menu, never a top-level item).

The `_select_x` handler builds a `SelectMenu`
([curses_menu.py](https://github.com/h8d13/archinstoo/blob/master/installer/archinstoo/lib/tui/curses_menu.py))
over a `MenuItemGroup` of `MenuItem`s
([menu_item.py](https://github.com/h8d13/archinstoo/blob/master/installer/archinstoo/lib/tui/menu_item.py)).

- single-select: returns `result.get_value()`, e.g.
  [`select_kb_layout`](https://github.com/h8d13/archinstoo/blob/master/installer/archinstoo/lib/menu/locale_menu.py).
- multi-select: pass `multi=True`, collect `result.get_values()` (often
  joined), e.g.
  [`select_xkb_options`](https://github.com/h8d13/archinstoo/blob/master/installer/archinstoo/lib/menu/locale_menu.py).

## Edit an existing install step

Three layers. The script (`perform_installation`) owns step order and
gates each step on its config. `Installer`
([installer.py](https://github.com/h8d13/archinstoo/blob/master/installer/archinstoo/lib/installer.py))
owns target, pacman, kernel params, fstab entries and teardown, and exposes
one thin method per step. The module named for the area does the work.
Edit the module, keep the entry, unless reordering.

`Installer.__exit__` on a clean exit runs `report_outcome` over
`_helper_flags`: `base` is set by `minimal_installation()`, `bootloader` by
`add_bootloader()`, and a flag still `False` is reported as a step not
reached. Scripts that skip those steps claim the flag with
`set_helper_flag` (live/packages target `/`, format stops after mount).

| Step | Lives in |
|---|---|
| mount layout, key files, TPM2/FIDO2 enrollment, fstab, snapshots | `disk/` (`mount`, `keyfiles`, `cryptenroll`, `fstab`, `snapshots`) |
| initramfs, swap file, zram, sysctl | `kernel/` |
| bootloaders, UKI, kernel cmdline | `bootloader/install.py` |
| users, sudo/doas, stash clone | `authentication/accounts.py`, `authentication/stash.py` |
| locale, vconsole, keyboard, timezone | `localization/configure.py` |
| services (enable/disable, user units, linger) | `systemd.py` |
| mirrors, AUR bootstrap | `pm/mirrors.py`, `pm/aur.py` |
| ISO network copy, nic files, resolved | `network/network_handler.py` |

Primitives reused inside any step / app / profile (on `Installer`):

- `add_additional_packages(pkgs)`, `enable_service(name|list)`.
- `arch_chroot(cmd, run_as=None)`: run argv list in the target.
- `self.target` (`Path` of the new root), `self.handler.config` (full
  `ArchConfig`, e.g. read `app_config.firewall_config`).
- bootloader/keymap/fs: `add_bootloader()`, `set_keyboard()`,
  `minimal_installation()`, `genfstab()`.
