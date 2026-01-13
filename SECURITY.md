# Security

## User config

The real key to security is YOU being mindful.

1. Limit AUR usage to "known"
2. Common security practices
    - Firewall
    - Adblocking
    - Sysctl conf

3. Additionals
    - selinux
    - apparmor 
    - firejail
    - fail2ban
    - bubblewrap
    - flatseal

---

## Passwords/Users

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

Root account can optionally be locked in the TUI. 

---

## Guest users

Ex: sybling using the same system as you can set a user to have access to the same apps yet no terminal.

`useradd -m -s /bin/rbash guest`

Or with a password 

```
useradd -m -s /bin/rbash guest
passwd guest
```

