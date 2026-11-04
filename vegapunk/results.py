"""Write docs/results.md from what is in cache/: the numbers the README points to.

    uv run python -m vegapunk.results
"""

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from vegapunk import york
from vegapunk.rank import rank_all

CACHE = Path("cache")
OUT = Path("docs/results.md")


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def main() -> None:
    index = _load(CACHE / "index.json")
    hackathon = {n for v in index["issues"].values() for n in v}
    edison = {p.stem.removeprefix("pr-"): _load(p) for p in (CACHE / "edison").glob("pr-*.json")}
    hack = [e for k, e in edison.items() if k.isdigit() and int(k) in hackathon]
    verdicts = Counter(e["verdict"] for e in hack)
    lines = [f"# Vegapunk results", "", f"_Generated {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC from `cache/`._", "",
             "## Edison on the hackathon PRs", "",
             f"{len(hack)} of {len(hackathon)} competing PRs through the sandbox so far.", "",
             "| Verdict | PRs |", "|---|---|"]
    lines += [f"| {k} | {v} |" for k, v in verdicts.most_common()]
    ts = sum(1 for e in hack if e.get("ts_tests_not_run"))
    lines += ["", f"{ts} of them also change TypeScript tests, which Edison lists but does not run yet.", ""]

    bt = _load(CACHE / "backtest" / "score.json")
    lines += ["## Backtest: does Edison's evidence predict a merge?", ""]
    if bt:
        lines += [f"{bt['prs_scored']} past PRs that change switch-core tests (sampled half merged, half closed unmerged).", "",
                  "| Edison verdict | merged | closed | merge rate |", "|---|---|---|---|"]
        for k, v in sorted(bt["by_verdict"].items()):
            lines.append(f"| {k} | {v['merged']} | {v['closed']} | {bt['merge_rate_by_verdict'][k]:.0%} |")
        lines += ["", f"AUC (Edison + Atlas score as a merge predictor): **{bt['auc']}**; 0.5 is a coin flip.",
                  "Closed PRs are not all bad (some were superseded), so this is a floor, not a ceiling.", ""]
    else:
        lines += ["Not run yet.", ""]

    planted = _load(CACHE / "planted" / "results.json")
    lines += ["## Planted defects", ""]
    if planted:
        by = {}
        for v in planted.values():
            b = by.setdefault(v["kind"], [0, 0])
            if v["caught_by_edison"] is not None:
                b[0] += v["caught_by_edison"]
                b[1] += 1
        lines += ["| Planted fault | caught by Edison |", "|---|---|"]
        lines += [f"| {k} | {a}/{b} |" if b else f"| {k} | not Edison's job (see below) |" for k, (a, b) in by.items()]
        lines.append("")
        # synthetic tribunals (issue numbers >= 90000) pit a PR against its secret-planted twin
        for d in sorted((CACHE / "tribunal").glob("9????")):
            v = _load(d / "verdicts.json") or {}
            issue = _load(CACHE / "issues" / f"{d.name}.json") or {}
            twin = next((p for p in issue.get("prs", []) if p >= 90000), None)
            if twin is None:
                continue
            caught = [s for s, x in v.items()
                      if any(str(f).lower().startswith(("high", "critical")) for f in x.get("flags", {}).get(str(twin), []))]
            lines.append(f"Secret-planted twin #{twin} of #{twin - 90000} in a blind tribunal: flagged high/critical by "
                         f"{', '.join(caught) or 'nobody'}; reported by {', '.join(sorted(v)) or 'nobody yet'}.")
        lines.append("")
    else:
        lines += ["Not run yet.", ""]

    ranked = [r for r in rank_all() if len(r["ranking"]) > 1 and r["pick"] is not None]
    with_sats = [r for r in ranked if r["satellites_reporting"]]
    lines += ["## Tribunals", "", f"{len(ranked)} contested issues ranked; {len(with_sats)} with satellite verdicts.", ""]
    for r in with_sats:
        top = ", ".join(f"#{x['pr']} ({x['score']:.2f})" for x in r["ranking"] if x["score"] is not None)
        lines.append(f"- #{r['issue']} {r['title']}: {top}; pick #{r['pick']}, confidence {r['confidence']}"
                     + (f"; {'; '.join(r['disagreements'])}" if r["disagreements"] else ""))
    decisions = _load(CACHE / "decisions.json") or {}
    if decisions:
        agree = sum(next((r["pick"] for r in ranked if r["issue"] == int(i)), None) == d["pick"] for i, d in decisions.items())
        lines += ["", f"Stella's recorded picks: {len(decisions)}; Vegapunk's pick matched {agree}."]
    sealed = sorted(Path("predictions").glob("*.sha256")) if Path("predictions").exists() else []
    lines += ["", "## Sealed predictions", ""]
    lines += [f"- `{p.name}`: `{p.read_text(encoding='utf-8').split()[0]}`" for p in sealed] or ["None yet."]
    spend = york.report()
    lines += ["", "## Cost", "", f"Paid model spend: ${spend['spent_usd']:.4f} of the ${spend['cap_usd']:.2f} cap "
              f"({sum(v['calls'] for v in spend['by_purpose'].values())} gpt-4o-mini calls). "
              "Claude (Shaka) and Gemini (Lilith) run on existing subscriptions.", ""]
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(OUT)


if __name__ == "__main__":
    main()
