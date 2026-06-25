#!/usr/bin/env bash
# FarmToWin wrapper for Prism Launcher.
#
# Prism builds the Minecraft launch command itself, then (if set) runs it through
# a "Wrapper command". Prism invokes this script as:
#     prism-wrapper.sh <java> <all the jvm/game args...>
# We do a fresh ZenCraft login and rewrite --accessToken / --username / --uuid in
# that command with the real ZenCraft session, then exec it. The account Prism is
# configured with (use any offline account) is irrelevant - we override it here.
#
# One-time setup: ./farmtowin.sh setup   (stores your ZenCraft credentials)
# Then in Prism: Instance -> Edit -> Settings -> Custom commands ->
#   Wrapper command:  /absolute/path/to/prism-wrapper.sh
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CREDS="$HOME/.config/farmtowin/account"
PROFILE="$HERE/zencli/profile.json"
AUTOJOIN="${FARMTOWIN_AUTOJOIN:-play.zencraft.net}"   # set empty to disable auto-join

[ -f "$CREDS" ] || {
	echo "FarmToWin: no saved account. Run:  $HERE/farmtowin.sh setup" >&2
	exit 1
}
# shellcheck disable=SC1090
source "$CREDS"

# fresh ZenCraft login -> profile.json (token rotates, so do it now)
python3 "$HERE/zencli/zencli.py" login --email "$EMAIL" --password "$PASSWORD" >/dev/null

read -r NAME UUID TOKEN < <(python3 - "$PROFILE" <<'PY'
import json, base64, sys
p = json.load(open(sys.argv[1]))
print(p["name"], p["uuid"],
      base64.b64encode(f"{p['account_token']}:{p['fingerprint']}".encode()).decode())
PY
)

# rebuild Prism's command, overriding the identity fields
args=("$@")
out=()
j=0
while [ $j -lt ${#args[@]} ]; do
	a="${args[$j]}"
	out+=("$a")
	case "$a" in
		--username)    out+=("$NAME");  j=$((j+1)) ;;
		--uuid)        out+=("$UUID");  j=$((j+1)) ;;
		--accessToken) out+=("$TOKEN"); j=$((j+1)) ;;
	esac
	j=$((j+1))
done
[ -n "$AUTOJOIN" ] && out+=("--quickPlayMultiplayer" "$AUTOJOIN")

exec "${out[@]}"
