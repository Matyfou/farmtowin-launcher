#!/usr/bin/env bash
# FarmToWin Launcher - play ZenCraft on Linux with NO ZenLauncher, NO Wine.
#
# First run  : asks for your ZenCraft email/password once, saves them, installs
#              the game (MC 1.21.8 + Fabric + mods) and launches.
# Next runs  : instantly logs in and launches Minecraft, auto-joining the server.
#
# Saved credentials live in ~/.config/farmtowin/account (chmod 600), never in
# the repo. The ZenCraft session token rotates on each login, so we log in fresh
# and launch back-to-back with nothing else touching it.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GAME_DIR="$HOME/.local/.share/zencraft"          # must end with "zencraft" (mod check)
CONFIG_DIR="$HOME/.config/farmtowin"
CREDS="$CONFIG_DIR/account"
TEMPLATE="$HERE/zencli/game_command_template.txt"
PROFILE="$HERE/zencli/profile.json"
# Path baked into the captured launch template; rewritten to the local game dir.
TEMPLATE_DIR="/home/matyfou/.local/.share/zencraft"

# --------------------------------------------------------------------------- #
say() { printf '\033[36m>> %s\033[0m\n' "$*"; }
die() { printf '\033[31m!! %s\033[0m\n' "$*" >&2; exit 1; }

find_java() {
	local c v
	for c in "${ZEN_JAVA:-}" /usr/lib/jvm/java-21-openjdk/bin/java "$(command -v java || true)"; do
		[ -n "$c" ] && [ -x "$c" ] || continue
		v="$("$c" -version 2>&1 | head -1)"
		case "$v" in *'"21'*|*'version "21'*) echo "$c"; return 0 ;; esac
	done
	for c in /usr/lib/jvm/*21*/bin/java; do [ -x "$c" ] && { echo "$c"; return 0; }; done
	return 1
}

login_fresh() {   # logs in with saved creds, populates profile.json
	python3 "$HERE/zencli/zencli.py" login --email "$EMAIL" --password "$PASSWORD" >/dev/null
}

# --------------------------------------------------------------------------- #
JAVA="$(find_java)" || die "Java 21 not found. Install a JDK 21 (also needed: javac). Or set ZEN_JAVA=/path/to/java."
command -v javac >/dev/null || die "javac (JDK) not found - needed for the TLS helper. Install a JDK 21."
command -v python3 >/dev/null || die "python3 not found."

# 1. credentials -------------------------------------------------------------
if [ ! -f "$CREDS" ]; then
	say "First-time setup - log in to your ZenCraft account (saved locally, once)."
	read -rp "  email   : " EMAIL
	read -rsp "  password: " PASSWORD; echo
	[ -n "$EMAIL" ] && [ -n "$PASSWORD" ] || die "email/password required."
	say "Verifying login..."
	if ! login_fresh; then
		die "Login failed - wrong credentials, or the account/HWID does not match. Nothing saved."
	fi
	mkdir -p "$CONFIG_DIR"
	umask 077
	printf 'EMAIL=%q\nPASSWORD=%q\n' "$EMAIL" "$PASSWORD" > "$CREDS"
	chmod 600 "$CREDS"
	say "Credentials saved to $CREDS"
fi
# shellcheck disable=SC1090
source "$CREDS"

# 2. install game if missing -------------------------------------------------
if [ ! -f "$GAME_DIR/client.jar" ] || [ ! -f "$GAME_DIR/mods/zenauth-1.0.0.jar" ] \
	|| [ ! -f "$GAME_DIR/mods/fabric-api.jar" ]; then
	say "Installing the game (Minecraft 1.21.8 + Fabric + mods)... first time only."
	python3 "$HERE/zencli/install_game.py"
fi

# 3. fresh login -> account + token -----------------------------------------
say "Logging in as $EMAIL..."
login_fresh || die "Login failed. Delete $CREDS to re-enter your credentials."

read -r NAME UUID TOKEN < <(python3 - "$PROFILE" <<'PY'
import json, base64, sys
p = json.load(open(sys.argv[1]))
tok = base64.b64encode(f"{p['account_token']}:{p['fingerprint']}".encode()).decode()
print(p["name"], p["uuid"], tok)
PY
)
say "Account: $NAME ($UUID)"

# 4. build the launch command (portable paths) ------------------------------
say "Launching Minecraft (auto-join play.zencraft.net)..."
mapfile -t ARGS < <(grep -v '^===' "$TEMPLATE" | sed "/^$/d; s#${TEMPLATE_DIR}#${GAME_DIR}#g")
CMD=("$JAVA")
i=0
while [ $i -lt ${#ARGS[@]} ]; do
	a="${ARGS[$i]}"
	CMD+=("$a")
	case "$a" in
		--username)    i=$((i+1)); CMD+=("$NAME") ;;
		--uuid)        i=$((i+1)); CMD+=("$UUID") ;;
		--accessToken) i=$((i+1)); CMD+=("$TOKEN") ;;
	esac
	i=$((i+1))
done
CMD+=("--quickPlayMultiplayer" "play.zencraft.net")

cd "$GAME_DIR"
exec "${CMD[@]}"
