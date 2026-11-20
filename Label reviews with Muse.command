#!/bin/bash
# Double-click on a Mac. Asks for your Meta Model API key (hidden; used for this run only, never saved),
# has Muse read which way each wave-related review asks the game to move, and saves only those labels.
cd "$(dirname "$0")" || exit 1
python3 -c "import certifi" 2>/dev/null || python3 -m pip install --quiet --user certifi
read -r -s -p "Paste your Meta Model API key, then press Enter (it won't show): " MODEL_API_KEY; echo
export MODEL_API_KEY
python3 -m fanpulse.cli label --config games/mindustry/game.toml --posts mindustry_steam_reviews.json --theme enemy_waves \
  && echo "Done. Tell Claude: labels are ready." || echo "Something went wrong; copy the message above to Claude."
unset MODEL_API_KEY
read -r -p "Press Enter to close."
