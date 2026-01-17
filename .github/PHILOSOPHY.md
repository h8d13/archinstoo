# Just a tab of "Why"

Why would someone want to code 12h a day something like this..?

Rebuilding more with less
---

The idea was that with less complexity, we can build more stable experience and more possible paths.

This is a powerful idea because it would allow for standards to compete in better environment.

Providing choice should always be a priority, this makes for why, arch is arch.

Archinstall in its essence should behave similarly, giving all the options makes them all "right" to one's eyes.

This is also to illustrate that for example a feature that only 1% of users actually use should not be given priorities over modular architecture.

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










