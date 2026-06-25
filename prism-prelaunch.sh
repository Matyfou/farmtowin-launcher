#!/usr/bin/env bash
# FarmToWin pre-launch step for Prism Launcher.
#
# Prism launches Minecraft through its own NewLaunch entry point and feeds the
# account to it over stdin, so a wrapper can't patch --accessToken. Instead we
# log in here and drop the fresh ZenCraft session token into a file that the
# zenauth mod reads in-game (it ignores Prism's placeholder accessToken).
#
# One-time: ./farmtowin.sh setup        (stores your ZenCraft credentials)
# In Prism: Instance -> Edit -> Settings -> Custom commands ->
#   Pre-launch command:  /absolute/path/to/prism-prelaunch.sh
# Name your Prism *offline* account exactly your ZenCraft username.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CREDS="$HOME/.config/farmtowin/account"
SESSION="$HOME/.config/farmtowin/session"
PROFILE="$HERE/zencli/profile.json"

[ -f "$CREDS" ] || { echo "FarmToWin: no saved account. Run:  $HERE/farmtowin.sh setup" >&2; exit 1; }
# shellcheck disable=SC1090
source "$CREDS"

python3 "$HERE/zencli/zencli.py" login --email "$EMAIL" --password "$PASSWORD" >/dev/null

umask 077
python3 - "$PROFILE" "$SESSION" <<'PY'
import base64, json, sys
p = json.load(open(sys.argv[1]))
tok = base64.b64encode(f"{p['account_token']}:{p['fingerprint']}".encode()).decode()
open(sys.argv[2], "w").write(tok)
PY
echo "FarmToWin: session token written for $(python3 -c "import json;print(json.load(open('$PROFILE'))['name'])")"
