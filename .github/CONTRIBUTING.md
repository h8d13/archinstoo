# Contributing to archinstoo

## The project

### Get an overview

Best places are probably `args.py` and `scripts/` themselves. Then `installer.py`

### Code standards

Small patches are preferred, and need to be tested from scratch (ISO env + Host-2-Target)

### Structure

- Scripts

```
├── __init.py__
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

Therefore, guidelines and style changes to the code might come into effect as well as guidelines surrounding bug reporting and discussions. These are mostly there to try to help us figure out the actual issues and correct this in code in a perennial way.

## Branches

For each patch create a branch specifically targeted to fix something, `master` should stay clean and accept these patches if tested/reproduced.
It also means it should be the stable branch and single source of truth.

For your submitted patches you'll likely need to accomodate yourself with branches easily:
```
git checkout <existing>
git checkout -b <new>
git add <file(s)>
git commit 
# describe what this commit fixes, ideally one fix per commit
git push
```
Then open the PR with explenations too.

## Discussions

Currently, questions, bugs and suggestions should be reported through [GitHub issue tracker](https://github.com/h8d13/archinstoo/issues).<br>

## Coding convention

All rules/exlusions can be consulted in the master `pyproject.toml` file

Most of these style guidelines have been put into place after the fact *(in an attempt to clean up the code)*.<br>
There might therefore be older code which does not follow the coding convention and the code is subject to change.

## Git hooks

`archinstoo` ships pre-commit hooks that make it easier to run checks such as `mypy`, `ruff check`, and `flake8` locally.
The checks are listed in `.pre-commit-config.yaml` and can be installed via
```
pre-commit install
```

This will install the pre-commit hook and run it every time a `git commit` is executed.

You can also use tools directly locally or in IDEs extensions.

These might include stuff like: `ruff vulture mypy` etc. 

Can be consulted within [PCH](./.pre-commit-config.yaml)

## Submitting Changes

Archinstoo uses GitHub's pull-request workflow and all contributions in terms of code should be done through pull requests.
Direct pushes to master are premitted to code-owners.

Anyone interested in archinstoo may review your code. One of the core developers will merge your pull request when they
think it is ready. For every pull request, we aim to promptly either merge it or say why it is not yet ready; or edit it and merge directly.

To get your pull request merged sooner, you should explain why you are making the change (and small patches). 

For example, you can point to a code sample that is outdated in terms of Arch Linux command lines. 

It is also helpful to add links to online documentation or to the implementation of the code you are changing.
Any related digging/testing is actually just as useful as code.

Original Creator:
* Anton Hvornum ([@Torxed](https://github.com/Torxed))

Modified for archinstoo dev: [@h8d13](https://github.com/h8d13)
