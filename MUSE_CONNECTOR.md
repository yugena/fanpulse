# Using FanPulse from Meta Muse

FanPulse ships an MCP server (`fanpulse/muse_connector.py`). MCP is the format Muse uses to plug in outside tools. Once it's connected you can ask Muse things like:

> "What are Mindustry players complaining about most?"
> "Turn the top complaint into a code change and show me the diff."
> "Run a fresh scan and summarize what changed."

## Tools exposed
| Tool | What it does |
|---|---|
| `get_top_requests(limit, kind?)` | Ranked themes from the last scan, with example posts |
| `get_fix_proposal(theme_id)` | Senior-engineer proposal: diagnosis, fix, rollout, metrics, risks, code file list |
| `get_code_change(theme_id, run?)` | Verified code change: what players asked for, edits, measured before/after, diff |
| `get_code_file(name)` | Source for a proposal's C++ file |
| `run_scan(top_n)` | Re-collects from all enabled sources and re-ranks |

## 1. Host it over HTTPS
```bash
export FANPULSE_CONNECTOR_TOKEN=$(python -c "import secrets; print(secrets.token_urlsafe(32))")
export FANPULSE_CONFIG=games/mindustry/game.toml   # or games/gta6.toml; plus source keys for live data
python -m fanpulse.muse_connector --http --host 0.0.0.0 --port 8765
```
Put it behind HTTPS: a reverse proxy, Cloudflare Tunnel (`cloudflared tunnel --url http://localhost:8765`), or a small Fly.io/Render deployment. The endpoint is `https://<your-host>/mcp`, using streamable HTTP. Requests without `Authorization: Bearer <token>` get a 401.

## 2a. Personal use: a Muse custom connector
Muse has no "add MCP server" form. You ask it in plain language, and it builds the bridge and offers to save it as a reusable skill:

> Create a custom connector to FanPulse. It is a hosted MCP server over streamable HTTP at https://<your-host>/mcp and it requires an Authorization header: `Bearer <token>`.

Review the confirmation, say yes to saving it as a skill, and store the token in Muse's credential store when it asks. Meta doesn't review custom connectors, so only connect servers you control.

## 2b. Public listing: the Muse connector directory
Submit at **muse.ai/platform**. On the Technical specs tab, choose **MCP**, then enter the endpoint, documentation link and access requirements. Meta reviews functional, security and legal requirements before a connector goes live. Before you submit:
- [ ] Replace the shared bearer token with per-user OAuth if strangers will use it.
- [ ] Tool descriptions say what each tool does and that proposals are for human review (already the case).
- [ ] Privacy policy: authors are stored only as one-way hashes, and raw usernames are never kept.
- [ ] Each data source's terms allow your use (Reddit's free API tier is non-commercial).

## Using Muse as the model too
Separately from the connector, FanPulse can use **Muse Spark** through Meta's Model API (OpenAI-compatible) to label posts the keyword rules missed and to draft proposals for new themes:
```bash
export MODEL_API_KEY=...                        # from dev.meta.ai
export FANPULSE_LLM_MODEL=muse-spark-1.3        # default; base URL https://api.meta.ai/v1
```
