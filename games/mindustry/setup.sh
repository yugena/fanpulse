#!/usr/bin/env bash
# One-time setup: Mindustry source + matching official server build + compiled probe.
# The tag and jar must match, so patched source compiles against the same classes it replaces.
set -euo pipefail
TAG="${1:-v160.8}"
cd "$(dirname "$0")/../.."
mkdir -p vendor games/mindustry/build
[ -d vendor/mindustry ] || git clone --depth 1 --branch "$TAG" https://github.com/Anuken/Mindustry.git vendor/mindustry
[ -f vendor/mindustry-server.jar ] || curl -fL -o vendor/mindustry-server.jar \
  "https://github.com/Anuken/Mindustry/releases/download/$TAG/server-release.jar"
javac -nowarn -cp vendor/mindustry-server.jar -d games/mindustry/build games/mindustry/Probe.java games/mindustry/WaveMetric.java
echo "ready: python -m fanpulse.cli trace --config games/mindustry/game.toml"
