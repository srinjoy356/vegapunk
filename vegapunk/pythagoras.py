"""Pythagoras: compares the competing PRs for one issue.

Deterministic part: size, files touched, and how much of each PR's added code also
appears in an earlier rival (a copy signal). Optional part: one gpt-4o-mini call per
issue, through York, for a one-line summary of each PR's approach.
"""

import json
import re
from pathlib import Path

from vegapunk import york

CACHE = Path("cache")
COPY_THRESHOLD = 0.6  # share of a PR's added lines already in an earlier rival
MIN_LINE = 12  # ignore short lines ("}", "return None") that every PR shares


def added_lines(diff: str) -> set[str]:
    return {l[1:].strip() for l in diff.splitlines()
            if l.startswith("+") and not l.startswith("+++") and len(l[1:].strip()) >= MIN_LINE}


def files_of(diff: str) -> list[str]:
    return re.findall(r"^diff --git a/\S+ b/(\S+)", diff, re.M)


def overlap(a: set[str], b: set[str]) -> float:
    """Share of a's lines that also appear in b."""
    return round(len(a & b) / len(a), 3) if a else 0.0


def compare(prs: list[dict], diffs: dict[int, str]) -> dict[int, dict]:
    """Per PR: size, files, overlap with each rival, and a copy flag against earlier rivals."""
    lines = {p["number"]: added_lines(diffs.get(p["number"], "")) for p in prs}
    order = {p["number"]: p["createdAt"] for p in prs}
    out = {}
    for p in prs:
        n = p["number"]
        rivals = {m: overlap(lines[n], lines[m]) for m in lines if m != n}
        earlier = {m: v for m, v in rivals.items() if order[m] < order[n]}
        copied_from = max(earlier, key=earlier.get) if earlier and max(earlier.values()) >= COPY_THRESHOLD else None
        out[n] = {"additions": p["additions"], "deletions": p["deletions"], "files": files_of(diffs.get(n, "")),
                  "overlap": rivals, "copied_from": copied_from}
    return out


def summarize(issue: dict, prs: list[dict], diffs: dict[int, str]) -> dict[str, str]:
    """One-line approach summary per PR from gpt-4o-mini; {} if York refuses or the call fails."""
    parts = [f"Issue #{issue['number']}: {issue['title']}\n{(issue['body'] or '')[:1500]}"]
    for c in issue["maintainer_comments"][-3:]:
        parts.append(f"Maintainer direction: {c['body'][:600]}")
    for p in prs:
        parts.append(f"PR #{p['number']} by {(p.get('author') or {}).get('login')}: {p['title']}\n"
                     f"{(p.get('body') or '')[:500]}\nFiles: {', '.join(files_of(diffs.get(p['number'], ''))[:15])}")
    prompt = "\n\n".join(parts)[:9000]
    try:
        text = york.chat([
            {"role": "system", "content": "You compare competing pull requests for one issue. Reply with JSON "
             "{\"<pr number>\": \"<one sentence: the approach, and anything it skips or adds beyond the issue>\"}."},
            {"role": "user", "content": prompt},
        ], purpose=f"pythagoras:{issue['number']}", json_mode=True)
        return {str(k): str(v) for k, v in json.loads(text).items()}
    except (york.CapReached, Exception) as e:  # summaries are optional; the deterministic part stands alone
        print(f"Pythagoras #{issue['number']}: no summaries ({e})")
        return {}


def run(issue_number: int, use_model: bool = True) -> dict:
    issue = json.loads((CACHE / "issues" / f"{issue_number}.json").read_text(encoding="utf-8"))
    prs = [json.loads((CACHE / "prs" / f"{n}.json").read_text(encoding="utf-8")) for n in issue["prs"]]
    diffs = {p["number"]: (CACHE / "prs" / f"{p['number']}.diff").read_text(encoding="utf-8")
             for p in prs if (CACHE / "prs" / f"{p['number']}.diff").exists()}
    result = {"issue": issue_number, "prs": {str(k): v for k, v in compare(prs, diffs).items()}}
    out_path = CACHE / "pythagoras" / f"issue-{issue_number}.json"
    old = json.loads(out_path.read_text(encoding="utf-8")) if out_path.exists() else {}
    heads = {str(p["number"]): p["headRefOid"] for p in prs}
    if use_model and len(prs) > 1:
        # one paid call per issue per set of heads
        result["summaries"] = old.get("summaries") if old.get("heads") == heads else summarize(issue, prs, diffs)
    result["heads"] = heads
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


if __name__ == "__main__":
    import sys
    for n in sys.argv[1:]:
        r = run(int(n))
        print(json.dumps({k: {"copied_from": v["copied_from"], "+": v["additions"]} for k, v in r["prs"].items()}),
              r.get("summaries", {}))
