#!/usr/bin/env python3
"""Standalone ZenCraft game installer (no launcher needed).

Downloads exactly what the ZenLauncher would install, using the official Mojang
and Fabric manifests, into ~/.local/.share/zencraft so zenplay.sh can launch it:
  - Minecraft 1.21.8 client.jar + libraries + assets (Mojang piston-meta)
  - Fabric loader 0.16.14 libraries (meta.fabricmc.net)
  - Fabric API + our zenauth bypass/auth mod (mods/)

The gameDir MUST end with "zencraft" (zenclient/our mod check). Linux natives
are pulled as the os-matched library jars; LWJGL extracts them at runtime.
"""

import concurrent.futures as cf
import json
import os
import shutil
import sys
import urllib.parse
import urllib.request
from pathlib import Path

MC_VERSION = "1.21.8"
LOADER_VERSION = "0.16.14"

GAME_DIR = Path.home() / ".local/.share/zencraft"
LIBS = GAME_DIR / "libraries"
ASSETS = GAME_DIR / "assets"
MODS = GAME_DIR / "mods"

VERSION_MANIFEST = "https://piston-meta.mojang.com/mc/game/version_manifest_v2.json"
FABRIC_PROFILE = f"https://meta.fabricmc.net/v2/versions/loader/{MC_VERSION}/{LOADER_VERSION}/profile/json"
RESOURCES = "https://resources.download.minecraft.net"
MODRINTH_FABRIC_API = (
    "https://api.modrinth.com/v2/project/fabric-api/version?"
    + urllib.parse.urlencode(
        {"game_versions": f'["{MC_VERSION}"]', "loaders": '["fabric"]'}
    )
)
HERE = Path(__file__).parent
ZENAUTH_JAR = next(
    (p for p in [
        HERE.parent / "mod/zenauth-1.0.0.jar",             # prebuilt (shipped)
        HERE.parent / "mod/build/libs/zenauth-1.0.0.jar",  # freshly built
    ] if p.exists()),
    HERE.parent / "mod/zenauth-1.0.0.jar",
)

OS_NAME = "linux"
OS_ARCH = "x86_64"


def get_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "zencli-installer"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def download(url: str, dest: Path, retries: int = 3) -> None:
    if dest.exists() and dest.stat().st_size > 0:
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    last = None
    for _ in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "zencli-installer"})
            with urllib.request.urlopen(req, timeout=60) as r:
                data = r.read()
            tmp = dest.with_suffix(dest.suffix + ".part")
            tmp.write_bytes(data)
            tmp.rename(dest)
            return
        except Exception as e:  # noqa: BLE001
            last = e
    raise RuntimeError(f"failed to download {url}: {last}")


def rule_allows(rules: list) -> bool:
    """Vanilla library OS rule evaluation for the current platform."""
    if not rules:
        return True
    allowed = False
    for rule in rules:
        os_rule = rule.get("os", {})
        name = os_rule.get("name")
        match = name is None or name == OS_NAME
        if rule.get("action") == "allow":
            allowed = allowed or match
        elif rule.get("action") == "disallow" and match:
            return False
    return allowed


def install_vanilla() -> None:
    print(f"[mojang] resolving {MC_VERSION}...")
    manifest = get_json(VERSION_MANIFEST)
    entry = next(v for v in manifest["versions"] if v["id"] == MC_VERSION)
    version = get_json(entry["url"])

    print("[mojang] client.jar...")
    download(version["downloads"]["client"]["url"], GAME_DIR / "client.jar")

    print("[mojang] libraries...")
    tasks = []
    for lib in version["libraries"]:
        if not rule_allows(lib.get("rules", [])):
            continue
        art = lib.get("downloads", {}).get("artifact")
        if art and art.get("url"):
            tasks.append((art["url"], LIBS / art["path"]))
    _parallel(tasks, "libraries")

    print("[mojang] asset index...")
    ai = version["assetIndex"]
    idx_path = ASSETS / "indexes" / f"{ai['id']}.json"
    download(ai["url"], idx_path)
    index = json.loads(idx_path.read_text())

    print(f"[mojang] assets ({len(index['objects'])} objects)...")
    atasks = []
    for obj in index["objects"].values():
        h = obj["hash"]
        atasks.append((f"{RESOURCES}/{h[:2]}/{h}", ASSETS / "objects" / h[:2] / h))
    _parallel(atasks, "assets")


def install_fabric() -> None:
    print(f"[fabric] loader {LOADER_VERSION} profile...")
    profile = get_json(FABRIC_PROFILE)
    tasks = []
    for lib in profile["libraries"]:
        group, artifact, ver = lib["name"].split(":")[:3]
        path = f"{group.replace('.', '/')}/{artifact}/{ver}/{artifact}-{ver}.jar"
        base = lib.get("url") or "https://maven.fabricmc.net/"
        if not base.endswith("/"):
            base += "/"
        tasks.append((base + path, LIBS / path))
    _parallel(tasks, "fabric libs")
    main_class = profile.get("mainClass")
    print(f"[fabric] mainClass = {main_class}")


def install_mods() -> None:
    MODS.mkdir(parents=True, exist_ok=True)
    print("[mods] fabric-api (modrinth)...")
    versions = get_json(MODRINTH_FABRIC_API)
    if not versions:
        raise RuntimeError("no fabric-api version for this MC")
    primary = next((f for f in versions[0]["files"] if f.get("primary")), versions[0]["files"][0])
    download(primary["url"], MODS / "fabric-api.jar")

    print("[mods] zenauth (bypass + auth packet)...")
    if not ZENAUTH_JAR.exists():
        raise RuntimeError(f"build the mod first: {ZENAUTH_JAR} missing")
    shutil.copy2(ZENAUTH_JAR, MODS / "zenauth-1.0.0.jar")


def _parallel(tasks: list, label: str) -> None:
    done = 0
    total = len(tasks)
    with cf.ThreadPoolExecutor(max_workers=16) as ex:
        futs = {ex.submit(download, url, dest): url for url, dest in tasks}
        for fut in cf.as_completed(futs):
            fut.result()
            done += 1
            if done % 50 == 0 or done == total:
                print(f"  {label}: {done}/{total}", flush=True)


def main() -> None:
    if GAME_DIR.name != "zencraft":
        sys.exit("gameDir must end with 'zencraft'")
    GAME_DIR.mkdir(parents=True, exist_ok=True)
    install_vanilla()
    install_fabric()
    install_mods()
    print(f"\ndone. game installed in {GAME_DIR}")


if __name__ == "__main__":
    main()
