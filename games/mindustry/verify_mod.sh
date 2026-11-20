#!/usr/bin/env bash
# Loads the Herald mod into Mindustry's real headless server and measures its effect with the game's own JS.
# Needs vendor/mindustry-server.jar (setup.sh). Prints: herald groups added (first load / reload) and metric changes.
set -euo pipefail
cd "$(dirname "$0")/../.."
S=$(mktemp -d); mkdir -p "$S/config/mods"; cp -r games/mindustry/mod "$S/config/mods/fanpulse-herald"
SCRIPT=$(tr '\n' ' ' < games/mindustry/mod_verify.js)
(sleep 6; echo "host Ancient_Caldera survival"; sleep 6; echo "js $SCRIPT"; sleep 8; echo "exit") \
  | (cd "$S" && java -jar "$OLDPWD/vendor/mindustry-server.jar") 2>&1 | sed 's/\x1b\[[0-9;]*m//g' | grep "herald groups"
