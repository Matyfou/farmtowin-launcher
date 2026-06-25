#!/usr/bin/env python3
"""ZenCraft CLI - Linux login + token builder for use with Prism Launcher.

Replicates the ZenCraft account flow reverse-engineered from zenlauncher.jar.
NETWORK CALLS (login/account) hit https://api.zencraft.cloud and ONLY run when
you explicitly invoke `login`. `hwid`, `status`, `token` are fully offline.

Auth flow (api.zencraft.cloud/webhook/<uuid>, POST JSON, verified live):
  1. INIT     e69f95c9-... -> 201 {"key": <sessionKey>}
  2. HWID     82af0c4c-... {key, hwid[], uuid} -> 201 {"f": <fingerprint>, "n": <relatedHwid>}
  3. LOGIN    af0d9ba1-... {key, f, m:email, p:password, totp?} -> 202 {"status", "token"}
  4. ACCOUNT  d66499b9-... {key, f, token} -> 200 {"name", "email", "game_id", "access_token"}

Calls to api.zencraft.cloud go through the bundled Java helper (ZenHttp): the
host filters non-JDK TLS fingerprints (Python/curl -> HTTP 400).

Game session accessToken (what the mod sends to the server) =
  base64( access_token + ":" + fingerprint )
"""

import argparse
import base64
import json
import subprocess
import sys
import uuid as uuidlib
from pathlib import Path

import hwid as hwidgen

HERE = Path(__file__).parent

API_BASE = "https://api.zencraft.cloud/webhook/"
EP_INIT = "e69f95c9-6955-4fd6-8391-8c4c3afea050"
EP_HWID = "82af0c4c-2736-453c-a765-0eedcdee0e05"
EP_LOGIN = "af0d9ba1-6b2b-4475-80f9-9748c62a14eb"
EP_ACCOUNT = "d66499b9-8902-4329-b08a-09cbcd5b71f3"

PROFILE_PATH = Path(__file__).parent / "profile.json"


# --------------------------------------------------------------------------- #
# Profile storage (local, offline)
# --------------------------------------------------------------------------- #
def load_profile() -> dict:
    if PROFILE_PATH.exists():
        return json.loads(PROFILE_PATH.read_text())
    return {}


def save_profile(p: dict) -> None:
    PROFILE_PATH.write_text(json.dumps(p, indent=2))
    print(f"profile saved -> {PROFILE_PATH}")


def ensure_seed(p: dict) -> str:
    if not p.get("hwid_seed"):
        p["hwid_seed"] = hwidgen.new_seed()
        print("generated new synthetic HWID seed (no real hardware read)")
    return p["hwid_seed"]


# --------------------------------------------------------------------------- #
# HTTP via Java helper (TLS-fingerprint gate on api.zencraft.cloud)
# --------------------------------------------------------------------------- #
def _ensure_helper() -> None:
    if not (HERE / "ZenHttp.class").exists():
        subprocess.run(["javac", "-d", str(HERE), str(HERE / "ZenHttp.java")], check=True)


def post(endpoint: str, body: dict | None) -> dict:
    _ensure_helper()
    data = json.dumps(body).encode() if body is not None else b""
    proc = subprocess.run(
        ["java", "-cp", str(HERE), "ZenHttp", API_BASE + endpoint],
        input=data,
        capture_output=True,
    )
    out = proc.stdout.decode(errors="replace")
    status_line, _, resp = out.partition("\n")
    try:
        status = int(status_line.strip())
    except ValueError:
        raise RuntimeError(f"java helper failed: {proc.stderr.decode()[:300]}")
    if status >= 400:
        raise RuntimeError(f"{endpoint} -> HTTP {status}: {resp[:200]}")
    return json.loads(resp) if resp.strip() else {}


# --------------------------------------------------------------------------- #
# Commands
# --------------------------------------------------------------------------- #
def cmd_hwid(args) -> None:
    p = load_profile()
    if args.new or not p.get("hwid_seed"):
        p["hwid_seed"] = hwidgen.new_seed()
    seed = p["hwid_seed"]
    save_profile(p)
    print("synthetic HWID set:")
    print(json.dumps(hwidgen.build_hwid(seed), indent=2))


def cmd_login(args) -> None:
    p = load_profile()
    seed = ensure_seed(p)
    hwid_set = hwidgen.build_hwid(seed)
    account_uuid = p.get("uuid") or str(uuidlib.uuid4())

    print("[1/4] init session key...")
    key = post(EP_INIT, None)["key"]

    print("[2/4] resolve HWID -> fingerprint...")
    r = post(EP_HWID, {"key": key, "hwid": hwid_set, "uuid": account_uuid})
    fingerprint = r.get("f") or r.get("fingerprint")
    related = r.get("n", 0)
    if related:
        print(f"  note: server reports {related} account(s) linked to this HWID")

    print("[3/4] login...")
    login_body = {"key": key, "f": fingerprint, "m": args.email, "p": args.password}
    if args.totp:
        login_body["totp"] = args.totp
    lr = post(EP_LOGIN, login_body)
    if lr.get("status") != "success" or not lr.get("token"):
        print(f"  login failed: {lr}", file=sys.stderr)
        sys.exit(1)

    print("[4/4] fetch account...")
    ar = post(EP_ACCOUNT, {"key": key, "f": fingerprint, "token": lr["token"]})
    name = ar.get("name")
    account_uuid = ar.get("game_id") or account_uuid
    account_token = ar.get("access_token") or lr["token"]

    p.update(
        {
            "name": name,
            "uuid": account_uuid,
            "fingerprint": fingerprint,
            "account_token": account_token,
        }
    )
    save_profile(p)
    print(f"\nlogged in as {name} ({account_uuid})")
    print(f"access token: {build_access_token(p)}")


def build_access_token(p: dict) -> str:
    raw = f"{p['account_token']}:{p['fingerprint']}"
    return base64.b64encode(raw.encode()).decode()


def cmd_token(args) -> None:
    p = load_profile()
    if not p.get("account_token") or not p.get("fingerprint"):
        print("not logged in - run `login` first", file=sys.stderr)
        sys.exit(1)
    print(build_access_token(p))


def cmd_launch(args) -> None:
    """Write the token into the Prism instance and launch it.

    NOTE: this connects to play.zencraft.net via Prism. Only the token file
    write is done here; the actual game launch is delegated to prismlauncher.
    """
    import subprocess

    p = load_profile()
    if not p.get("account_token") or not p.get("fingerprint"):
        print("not logged in - run `login` first", file=sys.stderr)
        sys.exit(1)

    mc_dir = Path(args.instance_dir).expanduser()
    if not mc_dir.exists():
        print(f"instance .minecraft dir not found: {mc_dir}", file=sys.stderr)
        print("run setup_instance.sh first", file=sys.stderr)
        sys.exit(1)

    token_file = mc_dir / "zentoken.txt"
    token_file.write_text(build_access_token(p))
    print(f"token written -> {token_file}")

    cmd = ["prismlauncher", "-l", args.instance_name, "-a", args.account or p.get("name")]
    print("launching:", " ".join(cmd))
    subprocess.run(cmd, check=False)


def cmd_status(args) -> None:
    p = load_profile()
    print(f"profile: {PROFILE_PATH}")
    print(f"  name        : {p.get('name', '-')}")
    print(f"  uuid        : {p.get('uuid', '-')}")
    print(f"  fingerprint : {'set' if p.get('fingerprint') else '-'}")
    print(f"  hwid_seed   : {'set' if p.get('hwid_seed') else '-'}")
    print(f"  logged in   : {bool(p.get('account_token'))}")


def main() -> None:
    ap = argparse.ArgumentParser(description="ZenCraft Linux CLI")
    sub = ap.add_subparsers(dest="cmd", required=True)

    h = sub.add_parser("hwid", help="show/generate synthetic HWID")
    h.add_argument("--new", action="store_true", help="force a new identity")
    h.set_defaults(func=cmd_hwid)

    lg = sub.add_parser("login", help="authenticate (NETWORK: hits the API)")
    lg.add_argument("--email", required=True)
    lg.add_argument("--password", required=True)
    lg.add_argument("--totp", help="2FA code if enabled")
    lg.set_defaults(func=cmd_login)

    sub.add_parser("token", help="print game access token").set_defaults(func=cmd_token)
    sub.add_parser("status", help="show profile state").set_defaults(func=cmd_status)

    ln = sub.add_parser("launch", help="write token + launch Prism (connects to server)")
    ln.add_argument("--instance-name", default="ZenCraft")
    ln.add_argument("--account", help="Prism account name (default: profile name)")
    ln.add_argument(
        "--instance-dir",
        default="~/.local/share/PrismLauncher/instances/ZenCraft/.minecraft",
        help="path to the instance .minecraft directory",
    )
    ln.set_defaults(func=cmd_launch)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
