#!/bin/bash
# Double-click on a Mac (or run in Terminal). Saves Mindustry's English Steam reviews
# (authors anonymized) next to this file.
cd "$(dirname "$0")" || exit 1
# python.org builds of Python on macOS have no CA certificates until certifi is installed.
python3 -c "import certifi" 2>/dev/null || python3 -m pip install --quiet --user certifi
echo "Fetching Mindustry Steam reviews (a few minutes)..."
python3 -m fanpulse.collectors.steam --appid "${1:-1127400}" --out mindustry_steam_reviews.json \
  && echo "Done. Tell Claude: reviews are ready." || echo "Something went wrong; copy the message above to Claude."
read -r -p "Press Enter to close."
