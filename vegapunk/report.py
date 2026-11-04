"""Render the docket as one self-contained HTML page: cache/report/index.html

    uv run python -m vegapunk.report
"""

import html
import json
from collections import Counter
from pathlib import Path

from vegapunk import york
from vegapunk.rank import rank_all

CACHE = Path("cache")
OUT = CACHE / "report" / "index.html"

CSS = """
:root{--bg:#f7f6f2;--card:#fff;--ink:#1d1b16;--muted:#6b665c;--line:#e4e0d6;--accent:#c4472f;--ok:#2f7d4f;--warn:#b07a12;--bad:#b3261e}
@media (prefers-color-scheme:dark){:root{--bg:#15140f;--card:#1f1d17;--ink:#ece8dc;--muted:#a29c8e;--line:#34312a;--accent:#e2765f;--ok:#6cc08b;--warn:#e0b04a;--bad:#ef7a72}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 system-ui,-apple-system,Segoe UI,sans-serif}
main{max-width:1100px;margin:0 auto;padding:32px 16px 64px}h1{font-size:28px;margin:0 0 4px}h2{font-size:19px;margin:36px 0 12px}
.sub{color:var(--muted);margin:0 0 24px}.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px}
.tile{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px}.tile b{display:block;font-size:24px}
.tile span{color:var(--muted);font-size:13px}.issue{background:var(--card);border:1px solid var(--line);border-radius:10px;margin:12px 0;overflow:hidden}
.issue summary{cursor:pointer;padding:12px 14px;display:flex;gap:10px;align-items:baseline;flex-wrap:wrap}.issue summary b{flex:1;min-width:200px}
.pill{font-size:12px;border-radius:99px;padding:2px 8px;border:1px solid var(--line);color:var(--muted);white-space:nowrap}
.pill.high{color:var(--ok);border-color:var(--ok)}.pill.medium{color:var(--warn);border-color:var(--warn)}.pill.low{color:var(--bad);border-color:var(--bad)}
.wrap{overflow-x:auto;padding:0 14px 14px}table{border-collapse:collapse;width:100%;font-size:13.5px}
th,td{text-align:left;padding:7px 8px;border-top:1px solid var(--line);vertical-align:top}th{color:var(--muted);font-weight:600}
.v-Proven{color:var(--ok)}.v-Broken{color:var(--bad)}.v-Unproven,.v-Unreproducible{color:var(--warn)}
.note{color:var(--muted);font-size:12.5px}a{color:var(--accent)}code{font-size:12.5px}
"""


def esc(x) -> str:
    return html.escape(str(x))


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def pct(x) -> str:
    return "–" if x is None else f"{x:.0%}"


def num(x) -> str:
    return "–" if x is None else f"{x:.2f}"


def tenths(x) -> str:
    """A 0..1 satellite signal shown back on its 0-10 scale."""
    return "–" if x is None else f"{x * 10:.0f}/10"


def render() -> Path:
    ranked = rank_all()
    index = _load(CACHE / "index.json")
    verdicts = Counter((_load(p) or {}).get("verdict") for p in (CACHE / "edison").glob("pr-*.json"))
    spend = york.report()
    bt = _load(CACHE / "backtest" / "score.json")
    contested = [r for r in ranked if len(r["ranking"]) > 1]
    tiles = [
        (len(index["issues"]), "hackathon issues"),
        (sum(len(v) for v in index["issues"].values()), "competing PRs"),
        (sum(verdicts.values()), "PRs through Edison's sandbox"),
        (verdicts.get("Proven", 0), "proven: fail before, pass after"),
        (len(contested), "issues ranked"),
        (f"${spend['spent_usd']:.3f}", f"paid model spend (cap ${spend['cap_usd']:.2f})"),
    ]
    parts = [f"<!doctype html><html lang=en><head><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'>"
             f"<title>Vegapunk Docket</title><style>{CSS}</style></head><body><main>",
             "<h1>Vegapunk docket</h1><p class=sub>A council of Switch agents ranks the competing pull requests for each "
             "<a href='https://github.com/sandbox-quantum/switch/issues?q=label%3Ahackathon'>sandbox-quantum/switch hackathon issue</a>. "
             "A human makes the final call.</p><div class=tiles>"]
    parts += [f"<div class=tile><b>{esc(v)}</b><span>{esc(k)}</span></div>" for v, k in tiles]
    parts.append("</div>")
    if bt:
        rates = ", ".join(f"{esc(k)} {pct(v)} merged" for k, v in sorted(bt["merge_rate_by_verdict"].items()))
        parts.append(f"<h2>Backtest</h2><p>{bt['prs_scored']} past PRs (half merged, half closed unmerged) through Edison: "
                     f"{rates}. AUC of Edison + Atlas for predicting a merge: <b>{esc(bt['auc'])}</b> (0.5 = coin flip).</p>")
    parts.append("<h2>Issues</h2>")
    for r in sorted(contested, key=lambda r: -len(r["ranking"])):
        conf = r["confidence"] or "n/a"
        parts.append(f"<details class=issue><summary><span class=pill>#{r['issue']}</span><b>{esc(r['title'])}</b>"
                     f"<span class=pill>{len(r['ranking'])} PRs</span><span class=pill>pick #{esc(r['pick'])}</span>"
                     f"<span class='pill {esc(conf)}'>confidence {esc(conf)}</span></summary><div class=wrap><table>"
                     "<tr><th>#</th><th>PR</th><th>score</th><th>Edison</th><th>rivals' tests</th><th>Shaka</th>"
                     "<th>Lilith</th><th>Atlas</th><th>notes</th></tr>")
        tv = _load(CACHE / "tribunal" / str(r["issue"]) / "verdicts.json") or {}
        for i, row in enumerate(r["ranking"], 1):
            s, n = row["signals"], str(row["pr"])
            notes = [tv[k]["notes"][n] for k in ("shaka", "lilith") if n in tv.get(k, {}).get("notes", {})]
            if row["copied_from"]:
                notes.append(f"overlaps earlier #{row['copied_from']}")
            notes += row["high_flags"][:2]
            verdict = row["edison_verdict"] or ""
            parts.append(
                f"<tr><td>{i}</td><td><a href='https://github.com/sandbox-quantum/switch/pull/{n}'>#{n}</a></td>"
                f"<td>{num(row['score'])}</td><td class='v-{esc(verdict)}'>{esc(verdict or '–')}</td>"
                f"<td>{pct(s['cross'])}</td><td>{tenths(s['spec'])}</td><td>{tenths(s['safety'])}</td>"
                f"<td>{pct(s['atlas'])}</td><td class=note>{'<br>'.join(esc(x) for x in notes)}</td></tr>")
        parts.append("</table>")
        if r["disagreements"]:
            parts.append("<p class=note>" + "<br>".join(esc(d) for d in r["disagreements"]) + "</p>")
        parts.append("</div></details>")
    parts.append("<p class=note>Edison runs each PR's own tests in a no-internet sandbox on the PR and on its base. "
                 "Rivals' tests: share of competing PRs' tests this PR's code passes. Shaka judges the spec and the "
                 "maintainer's direction; Lilith red-teams. Missing signals are left out of the score.</p></main></body></html>")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("".join(parts), encoding="utf-8")
    return OUT


if __name__ == "__main__":
    print(render())
