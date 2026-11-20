#!/bin/bash
# Double-click on a Mac. Asks for your Meta Model API key (hidden; used for this run only, never saved),
# has Muse list every specific need in the negative and request reviews (~950 reviews, ~110 calls), then ranks
# them by how many different players share each one. Safe to stop and re-run: it resumes where it left off.
cd "$(dirname "$0")" || exit 1
python3 -c "import certifi" 2>/dev/null || python3 -m pip install --quiet --user certifi
read -r -s -p "Paste your Meta Model API key, then press Enter (it won't show): " MODEL_API_KEY; echo
export MODEL_API_KEY
python3 -m fanpulse.cli needs --config games/mindustry/game.toml --posts mindustry_steam_reviews.json \
  && echo "Done. Tell Claude: needs are ranked." || echo "Something went wrong; copy the message above to Claude (re-running resumes)."
unset MODEL_API_KEY
read -r -p "Press Enter to close."
