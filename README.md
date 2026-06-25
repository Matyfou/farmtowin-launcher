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

## Launch from Prism Launcher

Prism runs Minecraft through its own launcher entry point and feeds the account
over stdin, so a wrapper can't rewrite `--accessToken`. Instead, a **pre-launch**
step logs in and writes the fresh ZenCraft token to a file, and the `zenauth` mod
reads it in-game (ignoring Prism's offline placeholder token).

1. **Create the instance** — New Instance → Minecraft **1.21.8** → Mod loader
   **Fabric** (0.16.14 or newer).
2. **Add the mods** — in the instance, add **Fabric API** (Prism's mod browser or
   Modrinth), then **Add file** → `mod/zenauth-1.0.0.jar` from this repo.
3. **Account** — add an **Offline** account named **exactly your ZenCraft
   username** (that name is what the server sees).
4. **Save your ZenCraft credentials once**:
   ```
   ./farmtowin.sh setup
   ```
5. **Set the pre-launch command** — Instance → **Edit** → **Settings** →
   **Custom commands** → tick *Custom commands* → **Pre-launch command**:
   ```
   /absolute/path/to/farmtowin-launcher/prism-prelaunch.sh
   ```
   (Leave *Wrapper command* empty.)
6. **Play** — launch the instance from Prism. The pre-launch logs you in, the mod
   authenticates, and you connect to `play.zencraft.net`.

Notes:
- Needs system `python3` + a JDK 21 on `PATH` (the pre-launch does the login).
- The token is written to `~/.config/farmtowin/session` (chmod 600) and refreshed
  on every launch.
- The mod needs no special game directory, so a standard Prism instance is fine.
- Prism doesn't auto-join from the menu; open the server from the multiplayer
  list (or add it). The standalone `./farmtowin.sh` auto-joins.

## Layout

```
farmtowin.sh                     entry point (setup + launch)
prism-prelaunch.sh               Prism Launcher pre-launch command
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

## Account & hardware id

Just use any ZenCraft account — log in on first run and you're set.

The launcher sends a **synthetic hardware id** instead of scanning your real
machine (privacy). It's generated randomly the first time you log in and saved
in `zencli/profile.json` (kept out of git), so each install has its own stable
id — nothing is hardcoded or shared. See `zencli/hwid.py`.

It does **not** need to match the machine the account was created on: the id is
only required to be internally consistent within a session, which is why the
same account works across different PCs. The actual login is your e-mail and
password.

Creating a ZenCraft account is done through the official launcher (this project
only handles playing). Account creation isn't covered here.

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| `Java 21 not found` | install JDK 21 or set `ZEN_JAVA=/path/to/java21` |
| `javac not found` | install the full JDK (not just a JRE) |
| `Login failed` | wrong e-mail/password |
| `Session invalide…` in game | delete `zencli/profile.json` to regenerate the session, then relaunch |
| `401` errors in the log (profile key, Realms JWT…) | **normal** for a cracked account, harmless |

## Disclaimer

For personal, educational use. You must own a legitimate ZenCraft account.
Don't redistribute ZenCraft's proprietary launcher or assets.
