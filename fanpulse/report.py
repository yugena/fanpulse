"""Markdown + standalone HTML report."""
from __future__ import annotations

import base64
import html
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from .models import Cluster
from .proposals import proposal_for

KIND_LABEL = {"bug": "Bug", "feature_request": "Feature request", "qol": "Quality of life",
              "balance": "Balance", "performance": "Performance", "ops": "Ops / support"}


def build_markdown(clusters: list[Cluster], themes: dict, *, game: str, top_n: int = 8, allow_llm: bool = True) -> str:
    synthetic = any(p.synthetic for c in clusters for p in c.posts)
    total = sum(len(c.posts) for c in clusters)
    lines = [f"# FanPulse report: {game}",
             f"_Generated {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC · {total} classified posts_", ""]
    if synthetic:
        lines += ["> ⚠️ **DEMO DATA.** These posts are synthetic, written to exercise the pipeline. "
                  "The rankings show how the tool works. They are **not** real player sentiment. "
                  "Run a live scan before quoting any numbers.", ""]
    lines += ["## Top player requests", "",
              "| # | Theme | Type | Score | Mentions | Unique players | Platforms |",
              "|---|---|---|---|---|---|---|"]
    for i, c in enumerate(clusters[:top_n], 1):
        plats = ", ".join(f"{k} {v}" for k, v in sorted(c.platforms.items(), key=lambda kv: -kv[1]))
        lines.append(f"| {i} | {c.title} | {KIND_LABEL.get(c.kind, c.kind)} | {c.score:.1f} | "
                     f"{len(c.posts)} | {c.unique_authors} | {plats} |")
    lines += ["", "_Score = Σ over unique players of their best post's log-scaled engagement × recency decay, "
                  "× cross-platform bonus. One loud account can't inflate a theme._", ""]

    for i, c in enumerate(clusters[:top_n], 1):
        prop = proposal_for(c, themes, allow_llm=allow_llm)
        lines += ["---", f"## {i}. {c.title}", "",
                  f"**Type:** {KIND_LABEL.get(c.kind, c.kind)} · **Sentiment:** {c.sentiment:+.2f} · "
                  f"**Proposal:** {prop['source']}", "", "**What players are saying**" +
                  (" _(synthetic demo posts)_" if synthetic else "") + ":", ""]
        for p in c.top_examples(3):
            lines.append(f"- _{p.platform}, {p.likes} likes:_ {p.text[:220]}")
        # Nest proposal headings under this theme's heading (# -> ###, ## -> ####).
        body = re.sub(r"^(#{1,2}) ", lambda m: "##" + m.group(1) + " ", prop["markdown"].strip(), flags=re.M)
        lines += ["", body, ""]
        if prop["code_files"]:
            lines += ["**Code:** " + ", ".join(f"`proposals/code/{f}`" for f in prop["code_files"]), ""]
    return "\n".join(lines)


def build_html(markdown_text: str, title: str, assets: Path | None = None) -> str:
    """Self-contained HTML. Renders Markdown client-side with a tiny inline converter; images found in
    `assets` are embedded as data URIs so the page works as a single file (e.g. on a phone)."""
    if assets:
        def embed(m):
            f = assets / m.group(2)
            return f"![{m.group(1)}](data:image/png;base64,{base64.b64encode(f.read_bytes()).decode()})" if f.is_file() else m.group(0)
        markdown_text = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", embed, markdown_text)
    payload = json.dumps(markdown_text)
    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(title)}</title>
<style>
:root{{--bg:#0f0d14;--fg:#ece8f2;--mut:#a59fb3;--acc:#ff4fa3;--acc2:#2fd3c9;--card:#1a1622;--line:#2c2638}}
body{{margin:0;background:var(--bg);color:var(--fg);font:16px/1.6 system-ui,-apple-system,Segoe UI,Roboto,sans-serif}}
main{{max-width:900px;margin:0 auto;padding:32px 20px 80px}}
h1{{font-size:2rem;background:linear-gradient(90deg,var(--acc),var(--acc2));-webkit-background-clip:text;color:transparent}}
h2{{margin-top:2.2rem;border-left:4px solid var(--acc);padding-left:10px}} h3{{color:var(--acc2);font-size:1.25rem}} h4{{margin:1.2rem 0 .3rem;color:var(--fg)}}
table{{border-collapse:collapse;width:100%;font-size:.9rem;display:block;overflow-x:auto}}
th,td{{border-bottom:1px solid var(--line);padding:8px;text-align:left;vertical-align:top}}
th{{color:var(--mut);font-weight:600}} code{{background:var(--card);padding:2px 5px;border-radius:4px;overflow-wrap:anywhere}}
blockquote{{margin:1rem 0;padding:12px 16px;background:#2a1a24;border-left:4px solid var(--acc);border-radius:6px}}
hr{{border:0;border-top:1px solid var(--line);margin:2rem 0}}
pre{{background:var(--card);padding:12px;border-radius:8px;overflow-x:auto;font-size:.8rem;line-height:1.45}}
.add{{color:#5ee08a}} .del{{color:#ff7a8a}}
img{{max-width:100%;image-rendering:pixelated;border-radius:8px}} em{{color:var(--mut)}} li{{margin:.3rem 0}}
</style></head><body><main id="c"></main><script>
const md={payload};
function esc(s){{return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')}}
function inl(s){{return esc(s).replace(/!\\[([^\\]]*)\\]\\(([^)]+)\\)/g,'<img alt="$1" src="$2">').replace(/`([^`]+)`/g,'<code>$1</code>').replace(/\\*\\*([^*]+)\\*\\*/g,'<strong>$1</strong>').replace(/(^|[^*\\w])\\*([^*\\s][^*]*)\\*(?=[^*\\w]|$)/g,'$1<em>$2</em>').replace(/(^|\\W)_([^_]+)_(?=\\W|$)/g,'$1<em>$2</em>')}}
let out=[],list=null,tbl=null;
function flush(){{if(list){{out.push('<'+list.t+'>'+list.items.join('')+'</'+list.t+'>');list=null}}if(tbl){{out.push('<table>'+tbl.join('')+'</table>');tbl=null}}}}
let pre=null;
for(const raw of md.split('\\n')){{const l=raw.trimEnd();let m;
 if(/^```/.test(l)){{if(pre){{out.push('<pre>'+pre.join('\\n')+'</pre>');pre=null}}else{{flush();pre=[]}}continue}}
 if(pre){{pre.push(esc(raw).replace(/^([+-](?![+-]{{2}}).*)$/,(x)=>'<span class="'+(x[0]==='+'?'add':'del')+'">'+x+'</span>'));continue}}
 if(/^\\|/.test(l)){{if(/^\\|[-| ]+\\|$/.test(l))continue;const cells=l.slice(1,-1).split('|').map(c=>inl(c.trim()));
  const tag=tbl?'td':'th';tbl=tbl||[];tbl.push('<tr>'+cells.map(c=>'<'+tag+'>'+c+'</'+tag+'>').join('')+'</tr>');continue}}
 if((m=l.match(/^(#{{1,4}}) (.*)/))){{flush();out.push('<h'+m[1].length+'>'+inl(m[2])+'</h'+m[1].length+'>');continue}}
 if((m=l.match(/^\\s*[-*] (.*)/))){{if(!list||list.t!=='ul'){{flush();list={{t:'ul',items:[]}}}}list.items.push('<li>'+inl(m[1])+'</li>');continue}}
 if((m=l.match(/^\\d+\\. (.*)/))){{if(!list||list.t!=='ol'){{flush();list={{t:'ol',items:[]}}}}list.items.push('<li>'+inl(m[1])+'</li>');continue}}
 if((m=l.match(/^> ?(.*)/))){{flush();out.push('<blockquote>'+inl(m[1])+'</blockquote>');continue}}
 if(l==='---'){{flush();out.push('<hr>');continue}}
 if(!l){{flush();continue}} flush();out.push('<p>'+inl(l)+'</p>');}}
flush();document.getElementById('c').innerHTML=out.join('\\n');
</script></body></html>"""
