"""Sealed prediction: commit to a ranking now, prove later that it wasn't changed.

    uv run python -m vegapunk.seal seal                    # rank every issue, write the rankings, print the hash
    uv run python -m vegapunk.seal reveal <rankings.json>  # check the hash, score against the PRs actually merged

The rankings file stays private in cache/predictions/ until the maintainers have chosen.
Only predictions/<stamp>.sha256 (the fingerprint) is meant to be published right away,
for example in a commit and a social post. Our own PRs are left out of the rankings.
"""

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from vegapunk.github import GitHub
from vegapunk.rank import rank_all

CACHE = Path("cache")
PUBLIC = Path("predictions")


def canonical(data) -> bytes:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def our_login(gh: GitHub) -> str:
    login = os.environ.get("OUR_GITHUB_LOGIN")
    if not login:
        login = gh._request("GET", "/user").json()["login"]
    return login


def seal() -> Path:
    gh = GitHub()
    me = our_login(gh)
    issues = []
    for r in rank_all():
        rows = [x for x in r["ranking"]
                if (json.loads((CACHE / "prs" / f"{x['pr']}.json").read_text(encoding="utf-8")).get("author") or {})
                .get("login") != me]
        if len(rows) < 2:
            continue  # nothing to choose between
        issues.append({"issue": r["issue"], "ranking": [x["pr"] for x in rows],
                       "scores": {str(x["pr"]): x["score"] for x in rows}, "confidence": r["confidence"],
                       "satellites": r["satellites_reporting"]})
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    payload = {"sealed_at": stamp, "repo": "sandbox-quantum/switch", "excluded_author": me, "issues": issues}
    body = canonical(payload)
    digest = hashlib.sha256(body).hexdigest()
    private = CACHE / "predictions" / f"rankings-{stamp}.json"
    private.parent.mkdir(parents=True, exist_ok=True)
    private.write_bytes(body)
    PUBLIC.mkdir(exist_ok=True)
    (PUBLIC / f"{stamp}.sha256").write_text(
        f"{digest}  rankings-{stamp}.json\n"
        f"# Vegapunk sealed prediction: {len(issues)} issues of sandbox-quantum/switch with competing PRs.\n"
        f"# The rankings file is revealed after the maintainers choose; anyone can re-hash it:\n"
        f"#   sha256sum rankings-{stamp}.json\n", encoding="utf-8")
    print(f"sealed {len(issues)} issues\nsha256 {digest}\nprivate: {private}\npublic:  {PUBLIC / f'{stamp}.sha256'}")
    return private


MERGED_Q = "query($owner: String!, $name: String!) { repository(owner: $owner, name: $name) { %s } }"


def merged_states(gh: GitHub, numbers: list[int]) -> dict[int, bool]:
    out = {}
    for i in range(0, len(numbers), 50):
        chunk = numbers[i:i + 50]
        fields = " ".join(f"p{n}: pullRequest(number: {n}) {{ number merged }}" for n in chunk)
        data = gh.graphql(MERGED_Q % fields, owner="sandbox-quantum", name="switch")["repository"]
        out.update({v["number"]: v["merged"] for v in data.values() if v})
    return out


def reveal(path: Path) -> dict:
    body = path.read_bytes()
    stamp = json.loads(body)["sealed_at"]
    digest = hashlib.sha256(body).hexdigest()
    sealed = (PUBLIC / f"{stamp}.sha256").read_text(encoding="utf-8").split()[0]
    if digest != sealed:
        raise SystemExit(f"hash mismatch: file {digest} vs sealed {sealed}; the rankings were changed")
    payload = json.loads(body)
    gh = GitHub()
    merged = merged_states(gh, sorted({p for i in payload["issues"] for p in i["ranking"]}))
    rows, top1, top3 = [], 0, 0
    for i in payload["issues"]:
        winners = [p for p in i["ranking"] if merged.get(p)]
        if len(winners) != 1:
            continue  # not decided yet, or more than one merged
        w = winners[0]
        top1 += i["ranking"][0] == w
        top3 += w in i["ranking"][:3]
        rows.append({"issue": i["issue"], "merged": w, "predicted": i["ranking"][0], "rank_of_merged": i["ranking"].index(w) + 1})
    n = len(rows)
    result = {"sealed_at": stamp, "sha256": digest, "decided_issues": n,
              "top1": round(top1 / n, 3) if n else None, "top3": round(top3 / n, 3) if n else None, "rows": rows}
    (PUBLIC / f"rankings-{stamp}.json").write_bytes(body)
    (PUBLIC / f"reveal-{stamp}.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({k: result[k] for k in ("sealed_at", "sha256", "decided_issues", "top1", "top3")}, indent=1))
    return result


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("command", choices=["seal", "reveal"])
    ap.add_argument("file", nargs="?")
    args = ap.parse_args()
    if args.command == "seal":
        seal()
    else:
        reveal(Path(args.file))


if __name__ == "__main__":
    main()
