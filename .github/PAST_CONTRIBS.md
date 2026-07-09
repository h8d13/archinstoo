# Historical changes to upstream Archinstall

## Fork's origin

Divergence [point](https://github.com/archlinux/archinstall/pull/3997)
> At this point I wanted to add a lot of menu entries and remove some of the hardcoded defaults.

## Upstreamed

Issues tracker:

- Missing deps in linux-variant-headers

Reported [here](https://github.com/archlinux/archinstall/issues/4360)

Fixed same day [here](https://gitlab.archlinux.org/archlinux/packaging/packages/linux/-/work_items/188)

- Gnupg hang on `dirmngr` call

Reported [here](https://gitlab.archlinux.org/archlinux/packaging/packages/gnupg/-/work_items/13)

Fixed a week later [here](https://gitlab.archlinux.org/archlinux/packaging/packages/gnupg/-/commit/c1bee871ca9b1d6899da9279287b92654b698f30)

Pending upstream fixes:

- Modify existing `base-devel` pkg for `doas` or alternatives (`sudo` optional)

Reported [here](https://gitlab.archlinux.org/archlinux/packaging/packages/base-devel/-/work_items/7)

## Past solutions

Sending my patches upstream finally meant the months of testing something privately made sense to other people publicly.

The first step to this is **finding a bug**, for something I care enough about to devote a lot of time, focus and energy to.

The initial bug I found was that when installing from one computer to another (instead of from a USB), then rebooting it on another machine simply didn't work: it would get stuck at mounting drives for about 2 minutes.

[3599](https://github.com/archlinux/archinstall/issues/3599) # /etc/fstab boot hanging

> Bug was quickly reproduced by a maintainer, which made it worthy of fixing!

Opened this issue on Jun 15th and it got merged on Nov 9th, or 148 days later.
The fix was simply `man genfstab` and finding the right flag for what I needed: `-f` for filter, and repeating the destination.

```python
gen_fstab = SysCommand(f'genfstab {flags} -f {self.target} {self.target}').output()
```

I had found and patched this in my private repo for months but didn't know how or why to contribute it to public.

Then I wondered: are there other similar commands we miss flags for?
So I looked at other `SysCommand` calls (about 100 of them in total).

And I found this gem:

```python
pacstrap -C /etc/pacman.conf -K {self.target} {" ".join(packages)} --noconfirm
```

In the logs of any installation I kept seeing `Re-installing x, y`, due to selections having some overlap in dependencies.
Which is normal but useless compute. So I added `--needed` and logs properly showed `Skipping...`, which I was very happy about.

### More features, more problems

Now I have more that got pulled in:

[3930](https://github.com/archlinux/archinstall/commit/375d64a6001086dd0aeb22140e1e022247c33059) # snapper -> grub integration fix

[3928](https://github.com/archlinux/archinstall/commit/6b50815eb67c4c5fef9fa08c916be7884687427c) # Vconsole.conf KEYMAP= FONT= mkinitcpio v40 error

[3978](https://github.com/archlinux/archinstall/commit/6b23eff4226a7574e2d763aa3b49fdfb4153b75d) # Add host-to-target (H2T) installation mode detection

- Add `running_from_host()` function to detect if running from installed system vs ISO
- Function checks for `/run/archiso` existence (ISO mode) vs host mode
- Add clear logging of installation mode on startup
- Skip keyboard layout changes when running from host system
- Fix Pyright type error in jsonify() by using Any instead of object
- Update README to mention installation from existing system

This enables archinstall to be run from an existing Arch installation to perform host-to-target installs on other disks/partitions.

[4022](https://github.com/h8d13/archinstall-patch/commit/9e7a5f693108aad80a731bb719454547b97e50c9) # Do not install base-devel by default

A funny one I'm also very proud of: `base-devel` is more of a dev tool than a user's tool.
Building systems should explicitly state it as a dependency and not assume it's installed by default.
The first line of AUR helpers is often `sudo pacman -S git base-devel` anyway.

[4028](https://github.com/h8d13/archinstall-patch/commit/e5ccdb0c1c4495e63a7e1b5fe4b99c4a95c05cf8) # Adds a timer to post install screen

Because testing should be quick.

[4024](https://github.com/h8d13/archinstall-patch/commit/5fcea379b9cd1f65343056dcfd70a441dc0ab744) # Fix LVM creation/info

Hotfix for LVMs to not hang on `Setting up LVM config...`, which I had experienced myself.

[4005](https://github.com/h8d13/archinstall-patch/commit/1227babd8cf67750926df4bb75a8106a114a4693) # Change LVM /root def to adapt dynamically

Another hotfix where it was `20GiB` hardcoded.

[4007](https://github.com/h8d13/archinstall-patch/commit/17dc00185724d07a92abb19904c773ea95ea38c8) # Cache property of graphics_devices

You can see all work upstream [here](https://github.com/archlinux/archinstall/commits/master/?author=h8d13), and on gitlab where the more "serious" reports go.

----

## Building in the open

Here is what I've learned by building in the open.

- More issues -> fewer problems long-term
- More users -> more test cases

So how do we bridge this gap?

1. **Devtools**

In this category I see two main things:

One: overly complex issue categories, flows, reviews, and codebases, which slow down a project during traction.
Backwards-compat claims and style nits that make the code a magical piece instead, too few dare to touch. Instead of a place for fast iteration.

Two: amazing tools that are under-exploited should be made clearer to likely future contributors, especially local hooks such as shellcheck, ruff, etc.

2. **Systematic testing**

When a patch is released, or when edge occurrences need to be covered, testing has to be done in real-world conditions and from scratch.
This, plus logs/notes/screenshots and multiple scenarios, can often take more time than finding the fix in the first place.

It doesn't even account for two more factors: one, you need to understand and dig into the docs of the underlying issue(s) or related; two, you might need to test related changes several times over a matrix.

3. **Open**

From a philosophical standpoint this means _anyone_ can get involved, but moreover means they should be given the necessary information to do so.

This shouldn't mean complicated rules but instead welcoming guidelines that enhance success:

- **Issues:** user reports from issues AND other sources are the heart of the dev.
Taking real experience with a program helps us avoid other similar issues too. This naturally filters future issues to be more critical.

- **Contrib style:** in large established codebases you'll likely want to make targeted commits to specifics. Unless you're working on a mega patch (hehehe).

- **Reviews:** other maintainers will look at all of the code, and perhaps even test themselves on your branch.
Sometimes this means more changes are required, other times it might be logic related.

- **Implications:** with each change you make, however personal, you have to grasp other related code.
Searching the repo for defs/classes will help you trace, plus tracebacks when hitting errors (and again, proper testing according to changes).

- **Formats:** there are certain formats in place that help (simple issue format/categories).
Mentioning other PRs/issues/docs in discussions helps with traceability for other peers to look at quickly.

### Common issues

Often the best fixes are the ones we know for sure will occur again (reproducible and documented).
These are things we see from various sources and can either solve in code or make explicit in docs/UI.

In archinstall an example is that by default the timezone selected is `UTC`.
If the choice is wrong according to the user's real time and/or the hardware clock got reset (CMOS battery dead), then `gpg` verification of pkgs just fails.
A simple solution is to force the user to select a timezone by starting at `None` and making it mandatory, plus adding it to docs.

### Speed

Testing is annoying. Physical tests need you to flash the latest ISOs (monthly), go into BIOS, test install, grep logs, then reboot and verify.
Sometimes several times for one scenario.

So I thought, while I'm coding, this needs to be faster. Which needed two things:

**1.** a decent `QEMU` script to test different scenarios in VMs (the GUI managers needed more options)
**2.** an ISO with KDE files so I could test full desktop features in less time.

I even made it so the target would have `git` pre-installed with the repo already cloned in `sudo_user(0)` home.

Current best time is **1m54s**, achieved when I moved all the pkgs with hooks in the installer to the first base-strap.
Which you shouldn't do, for obvious reasons.

### Weird structure of an OS installer

The archinstall project is especially relevant to me because it covers thousands of use-cases in a TUI that could run on a potato or the latest most expensive hardware.

This makes it interesting: it covers a lot of ground, and has many options within (bootloaders, FS types, encryption, UKI, U2F keys, HSM, desktops/servers, etc).
These options are philosophy: a good starting point but barebones, due to arch being arch.

This places the installer in a weird position, kind of being downstream from everything.
But at the same time, breaking changes do occur in dev cycles, meaning testing here becomes both hell and fun.
Notably `systemd` or other major base libs (mkinitcpio, encryption libs) can break everything, or some rules change for x or y. This is often hotfixed in a few days and back to normal.

And in the end it's kind of **upstream of everything**, since different components have similar structure and do kind of compete.

Insert [xkcd comic](https://imgs.xkcd.com/comics/standards_2x.png) about competing standards.

[Archinstall](https://github.com/archlinux/archinstall) doesn't judge: it gives you all the options and you end up making your pizza.
And considering arch packages are basically live updates, let's just say it's fresh.
