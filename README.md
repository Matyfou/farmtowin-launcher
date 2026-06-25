# $FarmToWin$ Launcher

Play the **ZenCraft** Minecraft server (1.21.8) natively on **Linux** — no
ZenLauncher, no Wine, no Windows JRE.

You log in once, the launcher saves your account, installs the game, and from
then on a single command boots you straight onto `play.zencraft.net`.

```
git clone <this-repo> farmtowin-launcher
cd farmtowin-launcher
./farmtowin.sh
```

First run asks for your e-mail and password **once**. Every run after that
launches Minecraft instantly.

---

## What it does

The official ZenLauncher is a Windows-oriented JavaFX app that won't launch the
game on Linux. This project reproduces only what's needed to play:

1. **Auth** — talks to the ZenCraft account API and builds the in-game session
   token, exactly like the official client.
2. **Game install** — downloads Minecraft 1.21.8 + Fabric loader + Fabric API +
   assets straight from the official Mojang / Fabric / Modrinth manifests.
3. **`zenauth` Fabric mod** — a tiny mod that reproduces the server's auth
   handshake (and nothing else: no hardware scan, no telemetry).
4. **Launch** — runs the game with a Linux JRE and auto-joins the server.

## Requirements

- Linux x86_64
- **JDK 21** (both `java` and `javac` — the TLS helper is compiled on first run)
  - Arch: `sudo pacman -S jdk21-openjdk`
  - Debian/Ubuntu: `sudo apt install openjdk-21-jdk`
- `python3`
- ~500 MB free for the game (installed to `~/.local/.share/zencraft`)

If your `java` isn't version 21, point to it explicitly:

```
ZEN_JAVA=/usr/lib/jvm/java-21-openjdk/bin/java ./farmtowin.sh
```

## Usage

```
./farmtowin.sh
```

- **First run** — prompts for your ZenCraft e-mail/password, verifies the login,
  saves them to `~/.config/farmtowin/account` (`chmod 600`, never in the repo),
  installs the game, and launches.
- **Every run after** — logs in fresh (the session token is single-use) and
  launches immediately.

To change account, delete the saved credentials:

```
rm ~/.config/farmtowin/account
```

## Layout

```
farmtowin.sh                     entry point (setup + launch)
zencli/
  zencli.py                      ZenCraft login / token builder
  hwid.py                        synthetic hardware id (see "Account" below)
  install_game.py                downloads MC + Fabric + Fabric API + assets
  ZenHttp.java                   tiny HTTP helper (compiled on first run)
  game_command_template.txt      captured launch arguments
mod/
  zenauth-1.0.0.jar              prebuilt Fabric mod (used as-is)
  src/, build.gradle, ...        mod source (rebuild optional, see below)
```

Installed at runtime (outside the repo):

```
~/.local/.share/zencraft/        the Minecraft instance (client, libs, assets, mods)
~/.config/farmtowin/account      your saved credentials
```

## The `zenauth` mod

Lives in `mod/`, shipped prebuilt. Four small pieces, no hardware access:

- **LoginBypass** — skips the client-side Mojang session check (cracked account).
- **ClientBrand** — reports the client brand as `ZenLauncher` (the server rejects
  any other brand).
- **Auth handshake** — right before the connection's login phase, authorizes the
  session against the ZenCraft API. Timing matters: it runs at
  `ClientLoginConnectionEvents.INIT`, immediately before login.
- **Auth packet** — sends the session token to the server on join.

Rebuild it yourself (optional, needs JDK 21; Gradle/Loom will download Minecraft
and mappings on first build):

```
cd mod && ./gradlew build
cp build/libs/zenauth-1.0.0.jar ./zenauth-1.0.0.jar
```

## Account

The launcher authenticates with a **synthetic hardware id** kept in
`zencli/hwid.py` (`SPOOFED_HWID`) — your real hardware is never read. The catch:
the server binds each account to the hardware id it was **created** with, and the
in-game token must match it.

This repo ships the hardware id the bundled account was registered with, so it
works out of the box for that account. To use a different account, it has to be
registered against the same `SPOOFED_HWID` value. ZenCraft only allows
registration through the official launcher, which reads the real machine id;
the account here was created by running that launcher with `aq.class` patched to
return `SPOOFED_HWID` instead (so the server sees a brand-new machine), then
keeping the same id on the CLI side. That patching step is out of scope for this
repo and is not required for normal play.

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| `Java 21 not found` | install JDK 21 or set `ZEN_JAVA=/path/to/java21` |
| `javac not found` | install the full JDK (not just a JRE) |
| `Login failed` | wrong credentials, or the account wasn't created with the matching hardware id (see *Account*) |
| `Session invalide…` in game | the account/hardware-id pairing is off — see *Account* |
| `401` errors in the log (profile key, Realms JWT…) | **normal** for a cracked account, harmless |

## Disclaimer

For personal, educational use. You must own a legitimate ZenCraft account.
Don't redistribute ZenCraft's proprietary launcher or assets.
