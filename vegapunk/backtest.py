"""Backtest: does Vegapunk's evidence predict what maintainers actually did?

    uv run python -m vegapunk.backtest collect --sample 40   # pick merged and closed-unmerged PRs
    (in WSL)  uv run python -m vegapunk.edison --prs-file cache/backtest/index.json --atlas --jobs 2
    uv run python -m vegapunk.backtest score

Two questions, depending on what the repository's history holds:
- competing PRs: for issues with two or more PRs and exactly one merged, is Vegapunk's pick the merged one?
- merge prediction: across single PRs, are the ones Edison proves merged more often than the rest?
sandbox-quantum/switch has no decided competing-PR issues before the hackathon (every multi-PR
issue is a hackathon issue still open), so its backtest is merge prediction; the competing-PR
question is answered live by the sealed prediction instead.
Satellite verdicts are not used here: this measures the deterministic evidence alone.
"""

import argparse
import json
import random

from vegapunk.github import GitHub
from vegapunk.ingest import CACHE, linked_issues, paginate, write_json
from vegapunk.rank import atlas_signal, edison_signal

OUT = CACHE / "backtest"

ALL_PRS_Q = """
query($owner: String!, $name: String!, $after: String) {
  repository(owner: $owner, name: $name) {
    pullRequests(first: 100, after: $after, orderBy: {field: CREATED_AT, direction: DESC}) {
      pageInfo { hasNextPage endCursor }
      nodes {
        number title body state merged isDraft createdAt updatedAt url
        author { login } authorAssociation
        additions deletions changedFiles
        baseRefName baseRefOid headRefName headRefOid
        closingIssuesReferences(first: 10) { nodes { number } }
      }
    }
  }
}"""


def decided(prs: list[dict]) -> dict[int, list[dict]]:
    """Issues with >= 2 claiming PRs, exactly one merged and none still open."""
    by_issue: dict[int, list[dict]] = {}
    for pr in prs:
        for n in linked_issues(pr):
            by_issue.setdefault(n, []).append(pr)
    return {n: sorted(group, key=lambda p: p["createdAt"]) for n, group in by_issue.items()
            if len(group) >= 2 and sum(p["merged"] for p in group) == 1 and all(p["state"] != "OPEN" for p in group)}


def touches_core_tests(diff: str) -> bool:
    from vegapunk.edison.judge import CORE_TEST_RE
    import re
    return any(CORE_TEST_RE.match(f) for f in re.findall(r"^diff --git a/\S+ b/(\S+)", diff, re.M))


def collect(repo: str, sample: int, seed: int) -> None:
    owner, name = repo.split("/")
    gh = GitHub()
    prs = list(paginate(gh, ALL_PRS_Q, ("repository", "pullRequests"), owner=owner, name=name))
    print(f"{len(prs)} PRs scanned; decided competing-PR issues: {len(decided(prs))}")
    rng = random.Random(seed)
    pools = {True: [p for p in prs if p["merged"] and not p["isDraft"]],
             False: [p for p in prs if p["state"] == "CLOSED" and not p["merged"] and not p["isDraft"]]}
    chosen: dict[str, bool] = {}
    for merged, pool in pools.items():
        rng.shuffle(pool)
        taken = 0
        for p in pool:
            if taken >= sample // 2:
                break
            diff_path = CACHE / "prs" / f"{p['number']}.diff"
            if not diff_path.exists():
                diff_path.write_text(gh.diff(owner, name, p["number"]), encoding="utf-8", newline="")
            if not touches_core_tests(diff_path.read_text(encoding="utf-8")):
                continue  # nothing for Edison to prove; not a fair sample for this question
            write_json(CACHE / "prs" / f"{p['number']}.json", {**p, "linked_issues": sorted(linked_issues(p))})
            chosen[str(p["number"])] = merged
            taken += 1
    write_json(OUT / "index.json", {"repo": repo, "seed": seed, "prs": chosen})
    print(f"sampled {sum(chosen.values())} merged and {len(chosen) - sum(chosen.values())} closed-unmerged PRs "
          "that change switch-core tests")


def auc(pairs: list[tuple[float, bool]]) -> float | None:
    """Probability a random merged PR outscores a random closed one (ties count half)."""
    pos = [s for s, y in pairs if y]
    neg = [s for s, y in pairs if not y]
    if not pos or not neg:
        return None
    wins = sum((p > n) + 0.5 * (p == n) for p in pos for n in neg)
    return round(wins / (len(pos) * len(neg)), 3)


def score() -> dict:
    idx = json.loads((OUT / "index.json").read_text(encoding="utf-8"))
    by_verdict: dict[str, dict] = {}
    pairs, rows = [], []
    for n, merged in idx["prs"].items():
        e_path, a_path = CACHE / "edison" / f"pr-{n}.json", CACHE / "atlas" / f"pr-{n}.json"
        if not e_path.exists():
            continue
        e = json.loads(e_path.read_text(encoding="utf-8"))
        a = json.loads(a_path.read_text(encoding="utf-8")) if a_path.exists() else None
        v = by_verdict.setdefault(e["verdict"], {"merged": 0, "closed": 0})
        v["merged" if merged else "closed"] += 1
        signal = edison_signal(e)
        if signal is not None:
            atlas = atlas_signal(a)
            pairs.append((signal * 0.85 + (atlas if atlas is not None else 1.0) * 0.15, merged))
        rows.append({"pr": int(n), "merged": merged, "verdict": e["verdict"], "proven": e["proven"],
                     "broken": e["broken"], "atlas_added": (a or {}).get("added")})
    result = {"prs_scored": len(rows), "by_verdict": by_verdict,
              "merge_rate_by_verdict": {k: round(v["merged"] / (v["merged"] + v["closed"]), 3)
                                        for k, v in by_verdict.items()},
              "auc": auc(pairs), "rows": rows}
    write_json(OUT / "score.json", result)
    return result


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("command", choices=["collect", "score"])
    ap.add_argument("--repo", default="sandbox-quantum/switch")
    ap.add_argument("--sample", type=int, default=40)
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()
    if args.command == "collect":
        collect(args.repo, args.sample, args.seed)
    else:
        r = score()
        print(json.dumps({k: r[k] for k in ("prs_scored", "by_verdict", "merge_rate_by_verdict", "auc")}, indent=1))


if __name__ == "__main__":
    main()
