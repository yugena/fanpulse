#!/bin/bash
# Double-click on a Mac. Asks for your Meta Model API key (hidden; used for this run only, never saved).
# Muse reads the boss-warning feature spec plus the game code FanPulse located, and drafts the change.
# Claude then verifies the draft by compiling and running Mindustry's real code.
# If a feedback file from a failed verification is present, Muse gets it and repairs its draft.
cd "$(dirname "$0")" || exit 1
python3 -c "import certifi" 2>/dev/null || python3 -m pip install --quiet --user certifi
read -r -s -p "Paste your Meta Model API key, then press Enter (it won't show): " MODEL_API_KEY; echo
export MODEL_API_KEY
SPEC=games/mindustry/features/boss_warning.toml
FEEDBACK=out/mindustry/feature_boss_warning.feedback.json
PREV=(); [ -f "$FEEDBACK" ] && PREV=(--previous "$FEEDBACK") && echo "Repair round: giving Muse the last verification result."
echo "Muse is drafting the feature (a reasoning model, so this can take a few minutes)..."
python3 -m fanpulse.cli draft --config games/mindustry/game.toml --spec "$SPEC" "${PREV[@]}" \
  && echo "Done. Tell Claude: draft ready." || echo "Something went wrong; copy the message above to Claude."
unset MODEL_API_KEY
read -r -p "Press Enter to close."
