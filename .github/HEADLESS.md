# Headless options


## Intro 

Servers choices allow for flexible control over what you want to do.
You can select mutltiple profiles, if desired.

## Example 

In this example we'll set up a `tailscale` host to not have to do any port forwarding for Minecraft.

In server options select `tailscale` and `java`, you could create or select more profiles at this step.

Depending on what you are trying to achieve.

<img width="933" height="127" alt="image" src="https://github.com/user-attachments/assets/50ecb579-c8ab-4c09-b6c1-67f486ddc795" />

> You can also select a firewall for the host in `Applications`

- Get the server.jar file, agree to `eula.txt` set to `=true` in `/srv/minecraft/`

> Used the AUR version (`minecraft-server`) but you can also just get the raw file then ran `minecraftd start`

Then run `tailscale up` or `down` when turning the server off.

- Add your devices or friends to `tailscale`

For this I followed standard/official `install.sh` method to add clients.

<img width="1193" height="301" alt="image" src="https://github.com/user-attachments/assets/6d5143e6-c32e-4f0d-92dd-0a4669b14ebe" />

Launch the server and enjoy playing with your friends.

<img width="1715" height="478" alt="image" src="https://github.com/user-attachments/assets/e9487a15-f46f-4e13-999f-bed3eae0798c" />

Default port is `tailscale_ip:25565` 

## Containers/firewalls

Be sure to check you firewall configs if running several severs profiles.
You can also use stuff like `docker` or `podman` to manage this in a more efficient way.

Docker/Podman publish their own `iptables` chain that bypasses `ufw` but it still protects the host regardless.
Make sure to only enable needed ports or use reverse proxies.

---

## Others

You can apply  the same logic to remotely anything.

In instance `SteamCMD` to run other game servers, or other Linux native server binaries like `terraria`.
