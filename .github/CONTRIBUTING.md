# Contributing to archinstoo

## The project

### Get an overview

Best places are `args.py` and `scripts/*` themselves. Then `installer.py`
for the order of steps, and the package named for the area (`disk/`, `kernel/`,
`bootloader/`, `authentication/`, `localization/`, `pm/`, `network/`) for how a step works.

Each module gets a linked data structure in `models/`.

### Code standards

Small patches are preferred, and need to be tested (ISO env + Host-2-Target).
Unit tests run from the repo root: `pytest -c installer/pyproject.toml installer/tests`

Usually the first steps involve finding bugs, digging the actual causes or having a good idea!

### Structure

- Scripts

```
├── __init__.py
│   ├── scripts
│   │   ├── ...
```
These are used as a mods system, that can be used to run different kinds of installs/utilities.
Default being `guided` and `--script list` just returns all files in this dir.

- Config files only ever store all but disk encryption / auth info

The rest of classes/defs/files can be traced using global search inside `./installer/*`
This contains all the necessary logic and calls to different parts of the codebase to produce the final output.

## Contrib

Any contributions through pull requests are welcome as this project aims to be a community based project for Arch Linux.
If not for code, documentation changes, testing and digging up docs or command lines/ideas/discussions are also very welcome!

### You can also help by testing or suggesting ideas:

Many thanks to **@ShreshthTiwari, @dzamlo, @eososlinux** and some/many reddit/discord reporters too for the many indirect contribs.
Time spent testing or drawing up reports/digging information.

This in its core, takes just as much time as coding since often you need to test many scenarios.

Therefore, guidelines and style changes to the code might come into effect as well as rules surrounding bug reporting, discussions and PRs.
These are mostly there to try to help us figure out the actual issues and correct/improve this in code/docs, in a perennial way.

## Fork & Branches

For each patch create a branch specifically targeted to fix something, `master` should stay clean and accept these patches if tested/reproduced.
It also means it should be the stable branch and single source of truth.

For your submitted patches you'll likely need to get comfortable with `git` branches:
```shell
# fork first, or make sure it's up to date w/ master
git checkout <existing>
git checkout -b <new>
git add <file(s)>
git commit
# describe what this commit fixes, ideally one fix/feat/chore per commit
```

Then push and open the PR with explanations too, link to resources/issues.
If your commits are well scoped/documented you can skip most theatrics.

## Pre-commit hooks

`archinstoo` ships pre-commit hooks that make it easier to run checks such as `ruff` (fix, format, lint), `mypy`, `pylint`, `shellcheck` and `shfmt` locally.

The checks are listed in `.pre-commit-config.yaml` and can be installed via
```bash
pre-commit install
```

This will install the pre-commit hook and run it every time a `git commit` is executed.

You can also use tools directly locally or in IDE extensions.

Can be consulted within [PCH](https://github.com/h8d13/archinstoo/blob/master/.pre-commit-config.yaml)

Pre-commit requires `python-pylint` on the host: the pylint hook runs the system one
(pacman `python-pyparted` is already importable there). Other hooks pin their own venvs.

No host deps at all: open the repo in the [devcontainer](https://github.com/h8d13/archinstoo/tree/master/.devcontainer), docker is enough.

## Coding convention

All rules/exclusions can be consulted in the master `pyproject.toml` file

Most of these style guidelines have been put into place after the fact *(in an attempt to clean up the code)*.
There might therefore be older code which does not follow the coding convention and the code is subject to change.

A lot of these are also checked in CI.

Some style in the codebase includes: 80 chars soft limit in code (160 hard enforced), tab for indentation, 8 spaces for a tab (visually), no docstrings (inline comments).
Reduce duplicates and function grouping into clear models/utils/dispatchers.

## Submitting Changes

`archinstoo` uses GitHub's workflows and all contributions in terms of code should be done through pull requests.
Direct pushes to master are permitted to code-owners.

Anyone interested may review your code. One of the core developers will merge your pull request when they
think it is ready.

For every pull request, we aim to promptly either merge it or say why it is not yet ready; or edit it and merge directly.

To get your pull request merged sooner, you should explain why you are making the change (and small patches).

For example, you can point to a code sample that is outdated in terms of Arch Linux command lines.

It is also helpful to add links to online documentation or to the implementation of the code you are changing.
Any related digging/testing is actually usually just as useful as the code itself.

## AI Usage

Docs, testing and code should originate from your arguments/command lines usages/reflection.
Commit messages and PR bodies should also be written/reviewed by you. Ideally linked to issues/discussions/docs.

Low-effort and large changes without proper scoping/testing will be closed without explaining, same is true for issues.
Disclose usage/model in the PR/issues details and for what it was used (debugging, writing code, translating...).
Smaller reproduced fixes are more likely to be accepted than PRs that go in many directions or touch a lot of things.

## Discussions

Currently, questions, bugs and suggestions should be reported through [GitHub issue tracker](https://github.com/h8d13/archinstoo/issues).

### Testing

Early tests for repro I mostly use [TVM](https://github.com/h8d13/archinstoo/blob/master/TVM)
```shell
./TVM clean
./TVM #install
./TVM boot #check stuff
```

Similarly tested on actual hardware, once VM testing passes.

---

Original Creator:
* Anton Hvornum ([@Torxed](https://github.com/Torxed))

Modified By: [@h8d13](https://github.com/h8d13)

And finally thanks for being interested in `archinstoo` + good luck!
