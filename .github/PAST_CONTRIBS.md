# Historical changes to upstream Archinstall

## Upstreamed

Upstreamed fixes:

- Missing deps in linux-variant-headers

Reported [here](https://github.com/archlinux/archinstall/issues/4360)

Fixed same day [here](https://gitlab.archlinux.org/archlinux/packaging/packages/linux/-/work_items/188)

Pending upstream fixes:

- Modify existing `base-devel` pkg for `doas` or alternatives (`sudo` optional)

Reported [here](https://gitlab.archlinux.org/archlinux/packaging/packages/base-devel/-/work_items/7)

## Solutions

Sending my patches upstream... It finally meant the months of testing something privately, made sense to other people publicly.

And generally first step to this is **finding a bug**.

For something I care enough to devote a lot of time, focus and energy to.

The initial bug I had found was that when installing from one computer to another (instead of from a USB). Then rebooting it on another machine simply didn't work: it would get stuck at mounting drives for about 2 minutes.

https://github.com/archlinux/archinstall/issues/3599 # /etc/fstab boothanging

> Bug was quickly reproduced by a maintainer which made it worthy of fixing!

Opened this issue on Jun 15th and it got merged on Nov 9th or 148 days later. The initial fix was simply `man genfstab` and find the right flag for what I needed `-f` for filter and repeat the destination.

```python
gen_fstab = SysCommand(f'genfstab {flags} -f {self.target} {self.target}').output()
```

I obviously had found and patched in my private repo for months but didn't know how or why contribute it to public.

But then I wondered are there other similar commands we miss flags for? So I looked at other `SysCommand` calls (about 100~ of them in total out of a lot of code xd).

And I found this gem:

```python
pacstrap -C /etc/pacman.conf -K {self.target} {" ".join(packages)} --noconfirm
```

And in the logs of any installation I kept seeing: `Re-installing x, y` this due to selections have some overlap in dependencies which is totally normal but useless compute still. So I added `--needed` and logs properly showed `Skipping...` Which I was very happy about.

### more ******, more problems

Now I have more that got pulled in like snapper -> grub integration fix (#3930)

https://github.com/archlinux/archinstall/commit/375d64a6001086dd0aeb22140e1e022247c33059

Vconsole.conf KEYMAP= FONT= mkinitcpio v40 error:

https://github.com/archlinux/archinstall/commit/6b50815eb67c4c5fef9fa08c916be7884687427c

Add host-to-target (H2T) installation mode detection (#3978)

https://github.com/archlinux/archinstall/commit/6b23eff4226a7574e2d763aa3b49fdfb4153b75d

- Add `running_from_host()` function to detect if running from installed system vs ISO
- Function checks for `/run/archiso` existence (ISO mode) vs host mode
- Add clear logging of installation mode on startup
- Skip keyboard layout changes when running from host system
- Fix Pyright type error in jsonify() by using Any instead of object
- Update README to mention installation from existing system

This enables archinstall to be run from an existing Arch installation
to perform host-to-target installs on other disks/partitions.

Do not install base-devel by default (#4022)

https://github.com/h8d13/archinstall-patch/commit/9e7a5f693108aad80a731bb719454547b97e50c9

This is a funny one that I'm also very proud about is that `base-devel` is more of a dev tool than a user's tool. And building systems shoudl explicitly state it as a depandency and not assume it's installed by default. The first line of AUR helpers is often `sudo pacman -S git base-devel`

Adds a timer to post install screen (#4028)

https://github.com/h8d13/archinstall-patch/commit/e5ccdb0c1c4495e63a7e1b5fe4b99c4a95c05cf8

Because again testing should be quick.

Fix LVM creation/ info (#4024)

https://github.com/h8d13/archinstall-patch/commit/5fcea379b9cd1f65343056dcfd70a441dc0ab744

Hotfix for LVMs to not hang on `Setting up LVM config...` which I had experienced myself.

Change LVM /root def to adapt dynamically (#4005)

https://github.com/h8d13/archinstall-patch/commit/1227babd8cf67750926df4bb75a8106a114a4693

Another hotfix where it was `20GiB` hardcoded.

Cache property of graphics_devices (#4007)

https://github.com/h8d13/archinstall-patch/commit/17dc00185724d07a92abb19904c773ea95ea38c8

----

## Building in the open

Here is first what i've learned by building in the open.

- More Issues -> Less problems long-term
- More Users -> More tests cases

So how do we bridge this gap ?

1. **Devtools**

In this category i see two main things:

One overly complex issue categories, flows, reviews, codebase ... Which in turn slow down a project during traction.

Two amazing tools that are under-exploited should be made clearer to likely future contributors. Especially local hooks such as shellchecks, ruff, etc

2. **Systematic testing**

When a patch is released for something or when edge occurences need to be covered, testing has to be done in real-world conditions and from scratch. This itself, plus logs/notes/screenshots, multiple scenarios, can often take more time then finding the fix in the first place. This doesn't even take in consideration two more factors: one, you need to understand and dig into docs of underlying issue(s) or related and two, you night need to test related changes several times over.

3. **Open**

From a philosophical stand point this means _anyone_ can get involved, but more-over means should be given the necessary information to do so. This shouldn't mean complicated rules but instead welcoming guidelines that will enhance success.

- **Issues:** User reports from issues AND other sources are the heart of the dev. Taking real experience with a program helps us to avoid other similar issues too/improve continually. This naturally filters future issues to be more critical.

- **Contrib style:** in large established code-bases you'll likely want to make targeted commits to specifics, unless you're working on a mega patch (hehehe)...

- **Reviews:** Other maintainers will look at all of the code, and perhaps even test themselves on your branch. Sometimes this means more changes are required, othertimes might be logic related.

- **Implications:** With each change you make however personal, you have to grasp other related code. Obviously here searching repo for defs/classes will help you trace + tracebacks when hitting errors (and again proper testing according to changes).

- **Formats:** There are certain formats in place that help (simple issue format/categories), mentionning other PRs/issues/Docs in discussions helps with tracebility for other peers to look-at quickly.

---

The end of rabbit holes is where you decide to actually get interested in a subject and not just on it's surface level. this means repassage into something makes it easier to do or understand, you also have to be surrounded by said subject. Feel that it's natural for you to work towards.

## My experience this year (2025)

December 29th of 2024 was for me the first real 20 commits i ever made in a template repo for Python + NextJS, i had vibe-coded for real-time openCV image recognition. it had about 18fps on a laptop which was cool!

Since then i have pushed 7,886 times not counting other providers (for Alpine repos). Thats about 22 commits a day on average. And went maybe 10 days of holiday in total? Without earning single penny.

At the start, all i wanted was to save myself time, especially for future me, build interesting things that mattered, only to me. Useless or not, some of this code I 100% forgot about, some of it I still use/update day to day.

### Alpine Linux

On alpine, there it felt like you could understand how the system worked faster (at a lower level) since much of the documentation for OpenRC was so vast and complete (thanks gentoo users/alpine wiki).

**Do note:** many of the biggest frustations i've ever had on any Linux were solved by obscure blog posts from 2017 with 2 commenters that are now helping maintain said tool (jokes) but could be real lmao.

But then as bringus studios would say "are we gaming yet?" on these systems... Nvidia had dropped musl support also in December of 2024.

### Arch Linux

EUREKA moment was to make a script that can install arch from my alpine install: This was obviously a horrible idea. Because it meant i was still having to do a lot manually to be gaming. Decided otherwise instead would keep learning about systems and come back to it later.
I was also still using a lot of AI at the time.

This then lead me to `archinstall` (with many steps on way too many distros, so many in fact had to learn some `QEMU`). A piece of software that has many choices to, who knew, install arch linux.

It's a bit of a fit-all, miss-some kinda project. My first steps were to have notes on what to pick in the installer itself, and what to do first, after installing.

> I documented this in a project called ["KAES-ARCH"](https://github.com/h8d13/KAES-ARCH) which was just a large post install script for KDE/system.

---

### Simplicity

When first cloned archinstall it was overwhelming (to say the least)...

My hack: stripping about 60% of the codebase in a couple of hours (in a project I named ["Vase"](https://github.com/h8d13/Vase). Left only with critical parts that were of interest. This was probably the best choice and most rewarding thing: **1.** What was now missing were things i needed to understand, and **2.** the parts left were made more critical, readable/able to ingest.

Working from simple is also much easier, because I didn't have to care about something else breaking in the process. I could just test on repeat.

> But the more I strayed from upstream codebase the more I thought: if they do keep updating important parts, would bring conflicts everywhere and I'd need to resolve manually.

But here I had best of both worlds: a simple codebase where I can make crazier changes and the original to compare to.

I also contribute to an AUR helper called [grimoire](https://github.com/ryk4rd/grimoire).

---

### Impact

Sometimes coding is not about doing a lot, it's about doing what is "more" correct. And that is interesting as a couple of lines of code can have great impact on a lot of things. Both positevly and negatively.

I want to have positive impact that is systematic to changes that are needed for a clearer and more streamlined experience.

### Speed

Obviously testing is annoying, physical tests you need to flash latest ISOs (monthly), go into bios, test install, grep logs, then reboot verify. Sometimes do this several times for a scenario...

So I thought while I'm coding this needs to be faster. Which needed two things: **1.** a decent `QEMU` script to test different scenarios in VMs (don't like these GUI managers needed more options) and **2.** an ISO with KDE files so that I could test full Desktop features in less time.

Even made it so that the target would have `git` pre-installed with the repo already cloned in `sudo_user(0)` home.

Current best time is **1m54s** when I moved all the pkg with hooks in the installer to the first base-strap. Which you obviously shouldn't do for obvious reasons.

### Getting involved at any level

I think that's another great way to get involved is to test for others. Something I've done with powerpc64 archictecture, when a wizard releases software/firmware for it, I try it out for them and try to find any bugs or sometimes their stuff just doesn't work, and then I give out my hardware and what I tried.

Same for documentation, bug reporting and finally, even digging the right ressources when there is a problem somewhere, all important parts of a skill-set. This can include looking up commits, user reports on forums, etc

### Common issues

Often found that the best of fixes are the ones we know for sure will occur again (reproducible and documented). This means things that we see from various sources and can either solve in code are be made explicit in docs/UI.

In archinstall an example of this is that by default the timezone selected is `UTC`. If the choice is wrong according to user's real time and/or hardware clock got reset (CMOS battery dead) then `gpg` verification of pkgs just fails.

A simple solution is to force user to select a timezone by starting at `None` and making it mandatory + add it to docs.

### Purpose

The real win is that the more I can correct, the more I can also remove from said private repos I used in the meantime... Sometimes even remove full modules altogether because changes out of my control or from my changes allow for it.

### Weird structure of an OS installer

The project of archinstall is especially relevant to me because it covers thousands of use-cases in a TUI that could run on a potato or the latest most expensive hardware.

This makes it interesting, because one it covers a lot of ground but two has many options within (Bootloaders, FS types, encryption, UKI, U2F keys, HSM, Desktops/servers, etc, etc). These options are philosophy, it means a good starting point but barebones due to arch being arch.

Places the installer in a weird position kind of being downstream from everything, but at the same time, breaking changes do occur in dev cycles,  meaning testing here becomes both hell and fun, because you could create something new easily but you also need to see it through with many components.

Notably `systemd` or other major "base" libs (mkinitcpio, encryption libs, etc) changes that break everything period or some rules changed for x or y, etc. This is often hotfixed in a few days and back to normal. (This notably got me intrested in Artix dev too, where you can pick init system but keep familiarity of pacman)

And in the end is kind of upstream of everything, since different components have similar structure and do kind of compete in a way. Insert [xkcd comic](https://imgs.xkcd.com/comics/standards_2x.png) about competing standards

[Archinstall](https://github.com/archlinux/archinstall) doesn't judge it gives you all the options and you end up making your pizza. And considering arch packages are basically live updates, let's just say it's fresh.

### Edge

For both dev and gaming activities, reliability is quite important. The same is true even to common less technical users, for their use-case they need balance between performance, time and efficiency. Regardless of how, what or why, they want to see results and not have a headache. Some of my friends after playing at my place without any experience got into it just by showing them the actual system.
They like computers sure, dev too, but never thought further than oh it's MacOS or Windows.

This means being able to work, or enjoy entertainement with a system that is your own, that you can push or slow down to where you feel comfortable.

But *convenience* also is just as important ! That you are interested about your system but as to where you don't want to spend all of your time configuring instead of using, like me on said system. You'd have to love pain for that.

Which is why the extensive docs are so great because they can be used as reference but can also be improved upon (when newer standards for example appear).

Yet do not need to be super technical either if you just follow kinda "best practices" and like digging a little.

### Less on personal

This wide net of possibilities makes it so you have to be open-minded about the thousands of different paths an install can be, this is interesting as your ideals might totally differ from another person's and what is agreed to be optimal may not be the same either.

This is the strength of a single source of truth with many eyes looking at the code and almost infinite final results. And contributing to such a project is incredible. Simply put, I know that it will be useful and will avoid whatever frustrations I had, for others.

It also means you do not need to think about recognition or praise but just good code.

### Learn to debug

Skill issues or RTFM, Do it manually once at least and learn to use common tools such as `dmesg` and `journalctl`. Read man/docs and instructions when needed, follow tracebacks, learn terminal commands most importantly `|` to `less grep tail head`, etc

Follow symbols of code into a codebase (see how one piece of code can interact with X elements). See git providers of important libs or your suspects (their issues might be yours too).

And finally to contribute yourself learn to use git (branching merging etc) comfortably both for your own stuff simpler use, or for what you want to send in.

Funnily enough archinstall is [less popular nowadays](https://pkgstats.archlinux.de/packages/archinstall) with many automated installers (and the little need to re-use/download several times for the lambda user).

But the main strength I see, is **thousands of issues** referenced in code directly for all choices, hardware, etc.

### Community

There are some toxic elitists and trolls in the community and it's part of being a power-user centric, simplicity focused linux distribution, such an automated installer kind of opposes the manual way of doing things and some people dislike that.

A relevant example is when installing on weird hardware (let's say a G5 mac from 2005) then you'd use a `fdisk` but specifically needs `HFS` partitions labeled `apple bootstrap` or it would just not work as that is what `OpenFirmware` expects. Understanding here the origins can make for much faster debugging regardless of distro/install scripts.

Last I heard same [ppc-arch](https://archlinuxpower.org/) folks/wizards are making a Xbox360 port of arch that should be released soon (they were super friendly when I was struggling to install manually).

What I'm also saying is that if you go to the source, there are more specific communities around arch-subjectX.

But being helpful or trying to, and open to changes, that **enhance the next** person's life, is also less issues down the line, more interest, mirrors, donations, project and future for arch (and it's derivatives). Plus you get to be a good human being.

### Time

Just like a dev's workflow can seem quick to an outsider looking in, time is the only currency, and making an installer 3 minutes average over 10-15, seems important to me (since I need to test it n times) on top of it being more accurate towards edge cases.

This helps both dev and user but especially **testing** which again is probalby most time consuming !

Which made me release [this](https://github.com/h8d13/Vase/tree/master/vase_os/zazu_lago) a bit of a mess of code where it builds the standard ISO but with a profile pre-cached (simply a list of packages). In my testing case it's often KDE/Sound deps but could be anything. Also have my qemu stuff defined there.

### Nvidia plays well?

When I first switched my concern was that I only had Nvidia hardware at hand. Both a hybrid laptop (the worse nightmare of drivers not using the correct GPU) and Nvidia on desktop too, then with archinstall again made this simple: try different drivers, kernels (since DKMS builds agaisnt kernel-headers), and just see for myself when I'm happy with performances.

I still have an open pull request for hardware i would like to do.

That includes power profiles and VM enhancements. This also brought me to learn a bit about `nvidia-prime` and `nvidia-utils`.

### Giving back

Now when i started this post I said that it's also a time of year where we give back, but I think we should do that all year really... So I'll keep making more changes to my forks and trying to see how they can integrated into public code, whilst perhaps taking a small break for christmas (:)
But I will also prioritize my philosophy of being able to move fast, as anyone working on this or anything related is often a volunteer.

### Imposter syndrome

Think everybody that works on such things are always a bit OCD'esque as to everything that come their way. ANd this is only normal for some degree, as the responsability feels large and the knowledge needed is wide. But is also a strength in terms of double/triple checking what you do, or why you are doing it.

## More why ?

Because I use it everyday (when coding), under the tv and sometimes to play Counter Strike or similar titles with friends (who happen to see my performance and switch) couldn't see myself going back.
