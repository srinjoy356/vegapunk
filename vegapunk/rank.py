"""Combine every satellite's evidence into one ranking per issue.

Signals, each scaled to 0..1 (a missing signal is left out and the rest are re-weighted):
  edison  - fail-before/pass-after proof of the PR's own tests
  cross   - share of rivals' tests the PR's code passes (Edison's matrix)
  spec    - Shaka's score against the issue and the maintainer's direction
  safety  - Lilith's score (10 = nothing found)
  atlas   - no new lint/format/type errors
Penalties: Pythagoras copy flag, Lilith high-severity flags.
"""

import json
from pathlib import Path

CACHE = Path("cache")
WEIGHTS = {"edison": 0.30, "cross": 0.20, "spec": 0.30, "safety": 0.15, "atlas": 0.05}
EDISON = {"Proven": 1.0, "Unproven": 0.4, "No tests ran": 0.2, "No tests": 0.2, "Unreproducible": 0.3, "Broken": 0.0}
COPY_PENALTY = 0.15
HIGH_FLAG_PENALTY = 0.10


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def edison_signal(e: dict | None) -> float | None:
    if not e:
        return None
    base = EDISON.get(e["verdict"])
    if base is None:
        return None
    if e["verdict"] == "Proven" and e.get("passed"):
        # more of the PR's passing tests proving the change = stronger evidence
        base = 0.7 + 0.3 * e["proven"] / e["passed"]
    return round(base, 3)


def cross_signal(matrix: dict | None, pr: str) -> float | None:
    if not matrix:
        return None
    rates = [c["rate"] for c in matrix["cells"].get(pr, {}).values() if c["rate"] is not None]
    return round(sum(rates) / len(rates), 3) if rates else None


def atlas_signal(a: dict | None) -> float | None:
    if not a or "added" not in a:
        return None
    added = sum(a["added"].values())
    return round(max(0.0, 1 - added / 10), 3)


def satellite_score(verdicts: dict, satellite: str, pr: str) -> float | None:
    v = verdicts.get(satellite)
    if not v:
        return None
    s = v.get("scores", {}).get(pr)
    return None if s is None else max(0.0, min(1.0, float(s) / 10))


def high_flags(verdicts: dict, pr: str) -> list[str]:
    flags = []
    for v in verdicts.values():
        for f in v.get("flags", {}).get(pr, []):
            text = f if isinstance(f, str) else f"{f.get('severity', '')}: {f.get('issue', '')}"
            if text.lower().startswith(("high", "critical")):
                flags.append(text)
    return flags


def combine(signals: dict[str, float | None]) -> float | None:
    present = {k: v for k, v in signals.items() if v is not None}
    if not present:
        return None
    total = sum(WEIGHTS[k] for k in present)
    return sum(WEIGHTS[k] * v for k, v in present.items()) / total


def rank_issue(issue_number: int, use_satellites: bool = True) -> dict:
    issue = _load(CACHE / "issues" / f"{issue_number}.json")
    matrix = _load(CACHE / "edison" / f"matrix-{issue_number}.json")
    pyth = _load(CACHE / "pythagoras" / f"issue-{issue_number}.json") or {"prs": {}}
    verdicts = (_load(CACHE / "tribunal" / str(issue_number) / "verdicts.json") or {}) if use_satellites else {}
    rows = []
    for n in issue["prs"]:
        pr = str(n)
        e = _load(CACHE / "edison" / f"pr-{n}.json")
        signals = {
            "edison": edison_signal(e),
            "cross": cross_signal(matrix, pr),
            "spec": satellite_score(verdicts, "shaka", pr),
            "safety": satellite_score(verdicts, "lilith", pr),
            "atlas": atlas_signal(_load(CACHE / "atlas" / f"pr-{n}.json")),
        }
        score = combine(signals)
        copied = (pyth["prs"].get(pr) or {}).get("copied_from")
        flags = high_flags(verdicts, pr)
        if score is not None:
            score -= COPY_PENALTY * bool(copied) + HIGH_FLAG_PENALTY * min(2, len(flags))
        rows.append({"pr": n, "score": None if score is None else round(score, 3), "signals": signals,
                     "edison_verdict": (e or {}).get("verdict"), "copied_from": copied, "high_flags": flags})
    rows.sort(key=lambda r: (r["score"] is None, -(r["score"] or 0)))
    scored = [r["score"] for r in rows if r["score"] is not None]
    margin = round(scored[0] - scored[1], 3) if len(scored) > 1 else None
    picks = {s: v.get("ranking", [None])[0] for s, v in verdicts.items() if v.get("ranking")}
    top = rows[0]["pr"] if rows and rows[0]["score"] is not None else None
    disagreements = [f"{s} picked #{p}, combined pick is #{top}" for s, p in picks.items() if p and p != top]
    return {"issue": issue_number, "title": issue["title"], "ranking": rows, "pick": top, "margin": margin,
            "confidence": None if margin is None else ("high" if margin >= 0.15 else "medium" if margin >= 0.05 else "low"),
            "disagreements": disagreements, "satellites_reporting": sorted(verdicts)}


def rank_all(use_satellites: bool = True) -> list[dict]:
    index = _load(CACHE / "index.json")["issues"]
    return [rank_issue(int(n), use_satellites) for n in sorted(index, key=int) if index[n]]
