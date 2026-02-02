# Headless options

Servers choices allow for flexible control over what you want to do.

In this example we'll set up a `tailscale` host to not have to do any port forwarding for Minecraft.

0. In server options select `tailscale` and `java`

> You can also select a firewall for the host in `Applications`

1. Get the server.jar file, agree to `eula.txt` set to `=true` in `/srv/minecraft/`

> Used the AUR version (`minecraft-server`)

2. Add your devices or friends to `tailscale`

<img width="1193" height="301" alt="image" src="https://github.com/user-attachments/assets/6d5143e6-c32e-4f0d-92dd-0a4669b14ebe" />

Launch the server and enjoy playing with your friends.

<img width="1715" height="478" alt="image" src="https://github.com/user-attachments/assets/e9487a15-f46f-4e13-999f-bed3eae0798c" />


Default port is `tailscale_ip:25565`


---

You can apply  the same logic to remotely anything.

In instance `SteamCMD` to run other game servers, or other Linux native server binaries.