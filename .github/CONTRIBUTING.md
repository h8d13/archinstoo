# Contributing to archinstoo

## The project

### Get an overview

Best places are probably `args.py` and `scripts/` themselves. Then `installer.py`

### Code standards

Small patches are preferred, and need to be tested (ISO env + Host-2-Target).

Usually the first steps involve finding bugs or having a good idea!

Larger patches are okay too but need more thorough testing.

### Structure

- Scripts

```
├── __init__.py
│   ├── scripts
│   │   ├── ...
```
These are used as a mods system, that can be used to run different kinds of installs/utilities.
Default being `guided` and `--script list` just returns all files in this dir.

- Config files only ever store all but encryption / auth info

The rest of classes/defs/files can be traced using global search inside `./archinstoo/*`
This contains all the necessary logic and calls to different parts of the codebase to produce the final output.

## Contrib

Any contributions through pull requests are welcome as this project aims to be a community based project for Arch Linux.
If not for code, documentation changes, testing and digging up docs or command lines/ideas/discussions are also very welcome!

### You can also help by testing or suggesting ideas:

Many thanks to **@ShreshthTiwari, @dzamlo, @eososlinux** and some/many reddit/discord reporters too for the many indirect contribs.
Time spent testing or drawing up reports/digging info.
This in its core, takes just as much time as coding since often you need to test many scenarios.

Therefore, guidelines and style changes to the code might come into effect as well as rules surrounding bug reporting, discussions and PRs.
These are mostly there to try to help us figure out the actual issues and correct/improve this in code/docs, in a perennial way.

## Fork & Branches

For each patch create a branch specifically targeted to fix something, `master` should stay clean and accept these patches if tested/reproduced.
It also means it should be the stable branch and single source of truth.

For your submitted patches you'll likely need to accommodate yourself with `git` branches:
```shell
# fork first
git checkout <existing>
git checkout -b <new>
git add <file(s)>
git commit
# describe what this commit fixes, ideally one fix/feat per commit
git push
```
Then open the PR with explanations too, link to resources/issues.
If your commits are well scoped/documented you can skip most theatrics.

## Pre-commit hooks

`archinstoo` ships pre-commit hooks that make it easier to run checks such as `mypy`, `ruff check`, and `flake8` locally.
The checks are listed in `.pre-commit-config.yaml` and can be installed via
```bash
pre-commit install
```

This will install the pre-commit hook and run it every time a `git commit` is executed.

You can also use tools directly locally or in IDE extensions.

Can be consulted within [PCH](https://github.com/h8d13/archinstoo/blob/master/.pre-commit-config.yaml)

Pre-commit requires: `pkgconf` and `gcc` as well as `parted` on the host.

## Coding convention

All rules/exclusions can be consulted in the master `pyproject.toml` file

Most of these style guidelines have been put into place after the fact *(in an attempt to clean up the code)*.<br>
There might therefore be older code which does not follow the coding convention and the code is subject to change.

A lot of these are also checked in CI.

## Submitting Changes

Archinstoo uses GitHub's pull-request workflow and all contributions in terms of code should be done through pull requests.
Direct pushes to master are permitted to code-owners.

Anyone interested in archinstoo may review your code. One of the core developers will merge your pull request when they
think it is ready.

For every pull request, we aim to promptly either merge it or say why it is not yet ready; or edit it and merge directly.

To get your pull request merged sooner, you should explain why you are making the change (and small patches).

For example, you can point to a code sample that is outdated in terms of Arch Linux command lines.

It is also helpful to add links to online documentation or to the implementation of the code you are changing.
Any related digging/testing is actually just as useful as the code itself.

## AI usage

1. Docs, testing and code should originate from your arguments/command lines usages/etc
2. Low-effort and large changes without proper scoping will be closed without explaining
3. Disclose usage in the PR details and for what it was used (debugging, writing code, ...)

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
