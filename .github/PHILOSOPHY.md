# Just a tab of "Why"

Why would someone want to code 12h a day something like this..?

Rebuilding more with less
---

The idea was that with less complexity, we can build more stable experience and more possible paths.

This is a powerful idea because it would allow for standards to compete in better environment.

Providing choice should always be a priority, this makes for why, arch is arch.

Archinstall in its essence should behave similarly, giving all the options makes them all "right" to someone's eyes.

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

The same is true by removing `python-pydantic`, `python-cryptography` and `python-textual` from deps we can allow for a lighter package that actually only depends on `python-parted`.

Without losing any functionality.

Withstanding to-dos
---

Considering most people are volunteers who enjoy coding this stuff and have very little interaction with other contributors, aside from good or bad reviews... So I again needed a place where I can just scratch things off my list directly.

The first time around where I had done this to the codebase, I had removed too much... This time around, I was more careful, but still removed considerable parts, often in favor of something else. 

Code Quality
---

If anything PCH, general best practices help make the codebase more readable, not only that reduction itself, less hard coded defaults make for a more logical and pleasing flow of code. 

In the future, the more standards pop up the more this would make sense.
This is best illustrated by what I like to call "hidden documentation". 
Anything that is hardcoded is often something that is assumed and kind of gets lost as a standard with no competition.

This got me interested in both Artix and Alpine dev for openrc, runit and other init systems.

Anyways this is heavily underrated part of coding, once that choice is there and works, it is satisfying the next install de be able to pick.

Separation and pace
---

Two things that I needed with archinstall was for it to actually also be an installation medium creator. 

This allows for faster dev builds, more ram space in the ISO, and so on. This also creates a nice separation of concerns: dev build vs general usage.

The state of master branch should always be a single source of truth for everyone, this means that it evolves with how standards evolve, as fast as it can.
That it shouldn't be slowed down by some deprecated config or some nitpick on wording/styles. 

Dev
---

Whilst dev builds/branches... Well sometimes do some more "crazy" stuff like implementing bcachefs support just, as it's dropped out of kernel tree in .18 or supporting CachyOS kernels, or some random idea that sparked in the shower.

To conclude this I also think some priorities should be met, as working on visual changes should not be a priority to a codebase that moves fast, and has stuff that backlogs quite quickly. 

The future of such to me IS simplifying, and providing more tools, never settling for less.

Buried treasures
---

When I first realized I could just whip up any issues and start trying to fix stuff directly it was a thrill. 
Like I had a direct interface with the problem and possible solutions in code. This means fixing stuff for the long run.
Use cases that might not have been covered. Configurations that we had not thought of. 
Additional options that user might actually need for an operating system.

Outro
---

I don't really think a fork is ever considered something welcome, or truly maintainable, but again it's the only way I can think of to have a "safe space" both for my fixes or testing other's patches.
Anyways this allows me to test a bit faster and modify more behaviors to shorten testing.

Why
---

Archinstoo exists because fixing archinstall’s problems required more than incremental patches. Over time, architectural debt, backwards-compat constraints, and installer-first assumptions made certain classes of bugs, UX issues, and misconfigurations effectively unfixable without breaking existing behavior. 

This project started after contributing upstream and realizing that correctness, clarity, and explicit system modeling could not meaningfully coexist with those constraints (+ UI choices I disagree with, same for creds file). 

The goal of archinstoo is to be explicit instead of permissive, minimal instead of defensive (and bloated!), and intentional instead of heuristic-driven. Nothing is installed “just in case,” configuration is derived from actual capabilities, and users are expected to mean the choices they make. This trades broad approachability for predictable, debuggable systems and that trade-off is intentional.



