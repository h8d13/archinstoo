# Just a tab of "Why"

Why would someone want to code 12h a day something like this..?

Roots
---

When asked in 2005 whether he planned to automate more of the installation process — adding curses frontends, user creation wizards, etc — Judd Vinet, Arch's founder, replied:

> "Not really. A lot of people like our current installation script. One thing I'd like to have is a 'kickstart' style setup for sysadmins who install linux in labs or other settings where each install is more-or-less identical."
>
> — [The Big Arch Linux Interview, OSnews (March 2005)](https://www.osnews.com/story/10142/the-big-arch-linux-interview/)

He also said: *"Arch assumes you know what you're doing... it tends to stay out of your way."*

Archinstoo carries this forward. The installer exists to give you an OS, not to make decisions for you.
But it also exists to give you other tools you might need.

Rebuilding more with less
---

The idea was that with less complexity, we can build more stable experience and more possible paths.

This is a powerful idea because it would allow for standards to compete in better environment.

Providing choice should always be a priority, this makes for why, arch is arch.

Archinstoo in its essence should behave similarly, giving all the options makes them all "right" to someone's eyes.

This is also to illustrate that for example a feature that only 1% of users actually use should not be given priorities over modular architecture.

Some better examples:

Historically this list from `default_profiles/desktop.py`

```
	@property
	@override
	def packages(self) -> list[str]:
		return [
			'vi',
			'openssh',
			'wget',
			'iwd',
			'wireless_tools',
			'smartmontools',
			'xdg-utils',
		]
```
(Which I have already been tearing appart) 
Used to hardcode stuff like `htop vim wpa_supplicant ...`

My goal is this, to keep reducing hard-coded "standard" to choices/logic options.
The same is true with `base-devel` that used to be installed by default in archinstall.
But also pulled in `sudo` instead of giving liberty of choice there again.

But for 5 years makepkg and similar major upstream projects support alternatives and so should any code really.

```
  Commit: 2535611d6c3cbf951408c50ab35953efaf32f686
  Date: 2021-04-05
  Author: Eli Schwartz
  Subject: makepkg: add PACMAN_AUTH configurable setting for sudo elevation

  Bug tracker: Implements FS#32621

  Full commit message:
  If specified, this will be used no matter what. If not, then we check if sudo exists and use that, or else fall back on su.

  The feature request (FS#32621) is at: https://bugs.archlinux.org/task/32621
```
Anyways you start seeing the pattern... What is a 'standard' because it's actually needed, or what is a 'standard' because someone said it should be and left it in a file somewhere.

A recurring pattern in the old codebase was hard-coded defaults masquerading as necessity. Desktop profiles bundled networking tools, editors, and utilities regardless of environment or intent. Over time, this created hidden dependencies and undocumented behavior.

Major upstream projects have already moved away from this mindset. For example, makepkg has supported configurable privilege escalation for years. Archinstoo aligns with this reality: if alternatives are supported upstream, installers should not force a single path.

The same philosophy applies to dependencies. By removing unnecessary Python libraries and reducing the dependency surface to what is actually required, archinstoo becomes lighter, clearer, and no less capable.

The same is true by removing `python-pydantic`, `python-cryptography` and `python-textual` from deps we can allow for a lighter package that actually only depends on `python-parted`.

Without losing any functionality.

Withstanding to-dos
---

Working in a volunteer-driven project with limited feedback loops often means long-standing issues survive simply because they are hard to address incrementally. Archinstoo exists as a space where problems can be solved directly, not worked around.

The first major refactor removed too much. This iteration is more deliberate, but still unapologetic about removing code that exists only to preserve behavior rather than correctness. But still removed considerable parts, often in favor of something else. 

Code Quality
---

Hard-coded behavior acts as undocumented policy. Once embedded, it becomes invisible — accepted as “how things work” rather than questioned. Reducing these assumptions improves code readability, logical flow, and long-term adaptability.

This approach naturally opens the door to alternatives (and competing standards), different privilege models, and non-default environments. Once the choice exists and works, using it becomes both empowering and satisfying.

Separation and pace
---

Archinstoo also serves as its own installation medium builder. This separation allows faster development cycles, cleaner testing, and clearer boundaries between development and general usage.

The master branch is intended to be a single source of truth that evolves alongside the ecosystem. It should not be constrained by deprecated configurations or stylistic nitpicks that slow meaningful progress.

Dev
---

Development branches are intentionally experimental, sometimes exploring ideas that may never land upstream. This freedom enables rapid iteration and early testing of new technologies without burdening stable users.

In a fast-moving, deeply technical codebase, correctness and architecture must come first. And exeprimental features are fun to test:
Bcachesfs support when it was dropped by mr Torvalds, CachyOS kernel support, etc 

To conclude this I also think some priorities should be met, as working on visual changes should not be a priority to a codebase that moves fast, and has stuff that backlogs quite quickly. 

The future of such to me IS simplifying, and providing more tools, never settling for less.

Buried treasures
---

The moment it became possible to directly fix issues instead of negotiating around them, the project became a long-term investment. Archinstoo exists to uncover edge cases, support unconsidered configurations, and give users tools that actually reflect how operating systems are used in the real world.

Why
---

I don't really think a fork is ever considered something welcome, or truly maintainable, but again it's the only way I can think of to have a "safe space" both for my fixes or testing other's patches. Anyways this allows me to test a bit faster and modify more behaviors to shorten testing.

Archinstoo exists because fixing archinstall’s problems required more than incremental patches. Over time, architectural debt, backwards-compat constraints, and installer-first assumptions made certain classes of bugs, UX issues, and misconfigurations effectively unfixable without breaking existing behavior. 

This project started after contributing upstream and realizing that correctness, clarity, and explicit system modeling could not meaningfully coexist with those constraints (+ UI choices I disagree with, same for creds file). 

The goal of archinstoo is to be explicit instead of permissive, minimal instead of defensive (and bloated!), and intentional instead of heuristic-driven. Nothing is installed “just in case,” configuration is derived from actual capabilities, and users are expected to mean the choices they make. This trades broad approachability for predictable, debuggable systems and that trade-off is intentional.

The main controversy in the arch world is the following:

    - Users should always install manually once

This makes it easier for them to troubleshoot if they ever do run into an issue, and even contribute to installer related issues.
Bonus points for weird hardware that needed specific filesystems/bootloader, etc. 

    - But maintaining an install is just as valuable

Keeping an install clean, and/or making it what you need it to be, you will also learn a bunch. That is the beauty of arch, it is made for learners, who want control over their systems AND the latest.
At the cost of sometimes having to be more careful: ie, manual interventions/following update prints. As seen on [NEWS](https://archlinux.org/news/)
Countless times, but aside from that is pretty smooth sailing and the OS gets out of you way once you know what you are doing.


