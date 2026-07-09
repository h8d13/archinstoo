# Security

## Policy

### Supported Versions

Only the latest `master` is supported. Older tags receive no patches.

### Reporting a Vulnerability
Please do not open a public issue. hadean-eon-dev@proton.me

Or use GitHub's private vulnerability [reporting](https://github.com/h8d13/archinstoo/security/advisories/new).

> Expect an initial response **within 24 hours.**

---

## User config

The real key to security is YOU being mindful.

Some options are also given in the menu directly but **are always optional**.

1. Limit AUR usage to "known", review `PKGBUILD` AND post install scriplets.
2. Common security practices
    - Firewalls
    - VPNs
    - Adblocks
    - `sysctl` confs
    - SSH/Server hardenings

3. Additionals examples:
    - `apparmor`
    - `firejail`
    - `fail2ban`
    - `bubblewrap`
    - `flatseal`
    - `auditd`
    - `aide`
    - `tripwire`
    - your security stacks...

---

### Passwords/Users

Strong Passwords & Usernames

    Usernames/Hostnames: Avoid admin, user, root - use something descriptive unrelated to your identity.

Hostname has to be RFC-compliant for DNS (strict):

    Only: a-z, 0-9, - (hyphen)

Usernames are more flexible:

    Start with: a-z or _

    Followed by: a-z, 0-9, _, -

    Max 31 characters

    Can contain $ at the end (but breaks certain build scripts.)

    Passwords: Mixed case/numbers/symbols, or pw managers

    Root: Strong separate password, different from user accounts

Root account can **optionally be locked** in the TUI.

---

### Guest users

Ex: siblings using the same system as you can set a user to have access to the same apps yet no terminal.
In the menu you can simply create the user without elevated privileges and optionally `rbash`

### Laptop Encryption

Highly recommended in case of theft.

### U2F

You can enroll `pam.d` for passwordless auth/2FA/etc. Using keys such as:  YubiKey, Titan, SoloKey, Nitrokey
And use them for encryption too.

---

