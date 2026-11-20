#!/usr/bin/env bash
# One-time setup: Mindustry source + matching official server build + compiled probe.
# The tag and jar must match, so patched source compiles against the same classes it replaces.
set -euo pipefail
TAG="${1:-v160.8}"
cd "$(dirname "$0")/../.."
mkdir -p vendor games/mindustry/build
if [ ! -f vendor/mindustry/core/src/mindustry/game/Waves.java ]; then  # source tarball: no git needed
  mkdir -p vendor/mindustry
  curl -fsSL "${MINDUSTRY_SRC_URL:-https://github.com/Anuken/Mindustry/archive/refs/tags/$TAG.tar.gz}" \
    | tar xz --strip-components 1 -C vendor/mindustry \
  || { rm -rf vendor/.src && git clone -q --depth 1 --branch "$TAG" https://github.com/Anuken/Mindustry.git vendor/.src \
       && cp -R vendor/.src/. vendor/mindustry/; }
fi
[ -f vendor/mindustry-server.jar ] || curl -fL -o vendor/mindustry-server.jar \
  "https://github.com/Anuken/Mindustry/releases/download/$TAG/server-release.jar"
[ -f games/mindustry/build/WaveMetric.class ] || javac -nowarn -cp vendor/mindustry-server.jar -d games/mindustry/build games/mindustry/Probe.java games/mindustry/WaveMetric.java
echo "ready: python -m fanpulse.cli trace --config games/mindustry/game.toml"
