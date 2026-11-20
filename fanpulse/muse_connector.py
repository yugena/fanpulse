"""FanPulse as a connector for Meta Muse (and any other MCP client).

Muse accepts outside tools in two ways (as of Nov 2026):
  1. Custom connector: give Muse the HTTPS URL of this MCP server plus the token, and ask it to
     "create a custom connector". Muse builds the bridge and saves it as a reusable skill.
  2. Directory listing: submit the same endpoint at muse.ai/platform for Meta's review.
See MUSE_CONNECTOR.md for both flows.

Run:
  FANPULSE_CONNECTOR_TOKEN=<long-random> python -m fanpulse.muse_connector --http --port 8765
  python -m fanpulse.muse_connector            # stdio, for local MCP clients / testing
Expose the HTTP port over HTTPS (reverse proxy, Cloudflare Tunnel, Fly.io, etc.) before giving it to Muse.
"""
from __future__ import annotations

import argparse
import hmac
import json
import os
from pathlib import Path

try:  # MCP Python SDK 2.x
    from mcp.server.mcpserver import MCPServer as _Server
except ImportError:  # 1.x fallback
    from mcp.server.fastmcp import FastMCP as _Server  # type: ignore

from mcp.types import ToolAnnotations

from . import config, pipeline
from .proposals import proposal_for

CODE_DIR = Path(__file__).resolve().parents[1] / "proposals" / "code"
_CFG = config.load(os.environ.get("FANPULSE_CONFIG"))

server = _Server(
    name="fanpulse",
    title="FanPulse: player feedback to fix proposals",
    instructions=(
        "FanPulse aggregates player feedback about a video game from Reddit, Discord, Instagram and "
        "Facebook (official APIs only), ranks the most-requested fixes and features, and returns "
        "engineering fix proposals with C++ code. For games with a probe it also traces a theme to a "
        "measured code change (get_code_change). Call get_top_requests first; call run_scan only when "
        "the user asks for fresh data. Proposals and diffs are for human review. FanPulse never modifies game "
        "files. If a result says synthetic=true, tell the user it is demo data, not real player posts."
    ),
)

READ_ONLY = ToolAnnotations(readOnlyHint=True, openWorldHint=False)


def _clusters():
    try:
        return pipeline.load_cached(_CFG)
    except FileNotFoundError:
        return pipeline.scan(_CFG)


@server.tool(description="Collect fresh posts from all enabled sources and re-rank. Takes 1–5 minutes on live APIs.",
             annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, openWorldHint=True))
def run_scan(top_n: int = 8) -> dict:
    clusters = pipeline.scan(_CFG)
    return {"themes": [c.summary() for c in clusters[:top_n]]}


@server.tool(description="Ranked list of the most popular player requests/complaints from the last scan. "
                         "kind filters by bug|feature_request|qol|balance|performance|ops.",
             annotations=READ_ONLY)
def get_top_requests(limit: int = 5, kind: str | None = None) -> dict:
    cs = [c for c in _clusters() if kind is None or c.kind == kind]
    return {"themes": [c.summary() for c in cs[:max(1, min(limit, 25))]]}


@server.tool(description="Senior-engineer fix proposal for one theme (diagnosis, fix, rollout, metrics, risks), "
                         "plus the names of its C++ files. Use theme_id from get_top_requests.",
             annotations=READ_ONLY)
def get_fix_proposal(theme_id: str) -> dict:
    for c in _clusters():
        if c.theme_id == theme_id:
            return {"theme": c.summary(), **proposal_for(c, _CFG["themes"])}
    return {"error": f"unknown theme_id {theme_id!r}"}


@server.tool(description="The verified code change for a theme: what players asked for, the number changed in the "
                         "game's source, measured before/after metrics from running the real code, and a unified diff. "
                         "Set run=true to (re)compute it, which runs the game's probe and can take a few minutes.",
             annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, openWorldHint=False))
def get_code_change(theme_id: str, run: bool = False) -> dict:
    path = pipeline.out_dir(_CFG) / f"trace_{theme_id}.json"
    if run or not path.exists():
        if "trace" not in _CFG["themes"].get(theme_id, {}):
            return {"error": f"theme {theme_id!r} has no probe configured"}
        pipeline.trace(_clusters(), _CFG, theme_id)
    return json.loads(path.read_text())


@server.tool(description="Source of one proposal code file, e.g. police_spawn_fairness.cpp.", annotations=READ_ONLY)
def get_code_file(name: str) -> dict:
    path = (CODE_DIR / name).resolve()
    if path.parent != CODE_DIR.resolve() or not path.is_file():
        return {"error": "file not found", "available": sorted(p.name for p in CODE_DIR.iterdir())}
    return {"name": name, "language": "cpp", "source": path.read_text()}


# ---------------------------------------------------------------- HTTP + bearer auth
class BearerAuth:
    """Minimal ASGI guard: Muse custom connectors send the token you give them as a header."""

    def __init__(self, app, token: str):
        self.app, self.token = app, token.encode()

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            auth = dict(scope.get("headers", [])).get(b"authorization", b"")
            if not hmac.compare_digest(auth, b"Bearer " + self.token):
                await send({"type": "http.response.start", "status": 401,
                            "headers": [(b"content-type", b"application/json"),
                                        (b"www-authenticate", b"Bearer")]})
                await send({"type": "http.response.body", "body": b'{"error":"unauthorized"}'})
                return
        await self.app(scope, receive, send)


def http_app():
    token = os.environ.get("FANPULSE_CONNECTOR_TOKEN")
    if not token or len(token) < 24:
        raise SystemExit("Set FANPULSE_CONNECTOR_TOKEN to a random string of 24+ characters.")
    return BearerAuth(server.streamable_http_app(stateless_http=True, json_response=True), token)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--http", action="store_true")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8765)
    a = ap.parse_args()
    if a.http:
        import uvicorn
        uvicorn.run(http_app(), host=a.host, port=a.port)
    else:
        server.run("stdio")


if __name__ == "__main__":
    main()
