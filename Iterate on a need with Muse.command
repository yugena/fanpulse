#!/bin/bash
# Double-click on a Mac after "Rank needs with Muse". Pick a need by its rank; Muse plans the change, writes the
# acceptance checks from the players' words, drafts code, the real game code is compiled and run to measure it,
# and Muse checks player by player whether the change answers them, repairing up to 3 rounds.
# First run downloads Java 17 (into vendor/jdk, no admin rights) and the matching Mindustry source + server.
cd "$(dirname "$0")" || exit 1
python3 -c "import certifi" 2>/dev/null || python3 -m pip install --quiet --user certifi
if ! JAVA_HOME=$(/usr/libexec/java_home -v 17+ 2>/dev/null); then
  JAVA_HOME=$(ls -d "$PWD"/vendor/jdk/*/Contents/Home 2>/dev/null | head -1)
  if [ -z "$JAVA_HOME" ]; then
    echo "Downloading Java 17 (about 190 MB, one time)..."
    ARCH=$([ "$(uname -m)" = arm64 ] && echo aarch64 || echo x64)
    mkdir -p vendor/jdk && curl -fL "https://api.adoptium.net/v3/binary/latest/17/ga/mac/$ARCH/jdk/hotspot/normal/eclipse" | tar xz -C vendor/jdk || exit 1
    JAVA_HOME=$(ls -d "$PWD"/vendor/jdk/*/Contents/Home | head -1)
  fi
fi
export JAVA_HOME PATH="$JAVA_HOME/bin:$PATH"
bash games/mindustry/setup.sh >/dev/null || { echo "Game setup failed; copy the message above to Claude."; read -r -p "Press Enter to close."; exit 1; }
read -r -p "Which need (rank number from the ranking, Enter for 1)? " N
read -r -s -p "Paste your Meta Model API key, then press Enter (it won't show): " MODEL_API_KEY; echo
export MODEL_API_KEY
python3 -m fanpulse.cli iterate --config games/mindustry/game.toml --posts mindustry_steam_reviews.json --need "${N:-1}" \
  && echo "Done. Tell Claude: need ${N:-1} iterated." || echo "Something went wrong; copy the message above to Claude."
unset MODEL_API_KEY
read -r -p "Press Enter to close."
