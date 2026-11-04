"""Cache hackathon issues, the maintainers' direction comments and every competing PR.

    uv run python -m vegapunk.ingest [--repo owner/name] [--label hackathon] [--no-diffs]

Writes cache/issues/<n>.json, cache/prs/<n>.json, cache/prs/<n>.diff and cache/index.json.
Diffs are re-fetched only when a PR's head commit changes.
"""

import argparse
import json
import re
from pathlib import Path

from vegapunk.github import GitHub

CACHE = Path("cache")
MAINTAINER_ROLES = {"OWNER", "MEMBER", "COLLABORATOR"}
# GitHub's closing keywords; catches links GitHub itself doesn't record (e.g. PRs to non-default branches)
CLOSING_RE = re.compile(r"\b(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\s*:?\s+#(\d+)\b", re.I)

ISSUES_Q = """
query($owner: String!, $name: String!, $label: String!, $after: String) {
  repository(owner: $owner, name: $name) {
    issues(labels: [$label], first: 50, after: $after, states: [OPEN, CLOSED]) {
      pageInfo { hasNextPage endCursor }
      nodes {
        number title body state createdAt url
        author { login }
        assignees(first: 30) { nodes { login } }
        comments(first: 100) { nodes { author { login } authorAssociation body createdAt url } }
      }
    }
  }
}"""

PRS_Q = """
query($owner: String!, $name: String!, $after: String) {
  repository(owner: $owner, name: $name) {
    pullRequests(first: 100, after: $after, orderBy: {field: CREATED_AT, direction: DESC}) {
      pageInfo { hasNextPage endCursor }
      nodes {
        number title body state isDraft createdAt updatedAt url
        author { login } authorAssociation
        additions deletions changedFiles
        baseRefName baseRefOid headRefName headRefOid
        headRepository { nameWithOwner }
        closingIssuesReferences(first: 10) { nodes { number } }
      }
    }
  }
}"""


def paginate(gh: GitHub, query: str, path: tuple[str, ...], stop=None, **variables):
    """Yield nodes from a paginated GraphQL connection; stop(node) ends paging early."""
    after = None
    while True:
        conn = gh.graphql(query, after=after, **variables)
        for key in path:
            conn = conn[key]
        for node in conn["nodes"]:
            if stop and stop(node):
                return
            yield node
        if not conn["pageInfo"]["hasNextPage"]:
            return
        after = conn["pageInfo"]["endCursor"]


def maintainer_comments(issue: dict) -> list[dict]:
    """The comments that carry the maintainers' direction for an issue."""
    return [
        {"author": (c["author"] or {}).get("login"), "at": c["createdAt"], "url": c["url"], "body": c["body"]}
        for c in issue["comments"]["nodes"]
        if c["authorAssociation"] in MAINTAINER_ROLES
    ]


def linked_issues(pr: dict) -> set[int]:
    """Issues a PR claims to close: GitHub's recorded links plus closing keywords in the body."""
    numbers = {n["number"] for n in pr["closingIssuesReferences"]["nodes"]}
    numbers |= {int(m) for m in CLOSING_RE.findall(pr.get("body") or "")}
    return numbers


def link(issue_numbers: set[int], prs: list[dict]) -> dict[int, list[int]]:
    """Map each issue to the PRs that claim to close it, oldest PR first."""
    by_issue: dict[int, list[int]] = {n: [] for n in issue_numbers}
    for pr in sorted(prs, key=lambda p: p["createdAt"]):
        for n in linked_issues(pr) & issue_numbers:
            by_issue[n].append(pr["number"])
    return by_issue


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--repo", default="sandbox-quantum/switch")
    ap.add_argument("--label", default="hackathon")
    ap.add_argument("--no-diffs", action="store_true")
    args = ap.parse_args()
    owner, name = args.repo.split("/")
    gh = GitHub()

    issues = list(paginate(gh, ISSUES_Q, ("repository", "issues"), owner=owner, name=name, label=args.label))
    if not issues:
        raise SystemExit(f"No issues labelled {args.label!r} in {args.repo}")
    oldest = min(i["createdAt"] for i in issues)
    # PRs come newest first; nothing older than the oldest issue can close one of them
    prs = list(paginate(gh, PRS_Q, ("repository", "pullRequests"), stop=lambda p: p["createdAt"] < oldest,
                        owner=owner, name=name))
    by_issue = link({i["number"] for i in issues}, prs)
    competing = {n for nums in by_issue.values() for n in nums}

    for issue in issues:
        write_json(CACHE / "issues" / f"{issue['number']}.json", {
            "number": issue["number"], "title": issue["title"], "state": issue["state"], "url": issue["url"],
            "author": (issue["author"] or {}).get("login"), "created_at": issue["createdAt"], "body": issue["body"],
            "assignees": [a["login"] for a in issue["assignees"]["nodes"]],
            "maintainer_comments": maintainer_comments(issue),
            "prs": by_issue[issue["number"]],
        })

    fetched = 0
    (CACHE / "prs").mkdir(parents=True, exist_ok=True)
    for pr in prs:
        if pr["number"] not in competing:
            continue
        meta_path = CACHE / "prs" / f"{pr['number']}.json"
        old_head = json.loads(meta_path.read_text(encoding="utf-8")).get("headRefOid") if meta_path.exists() else None
        pr = {**pr, "linked_issues": sorted(linked_issues(pr))}
        diff_path = CACHE / "prs" / f"{pr['number']}.diff"
        if not args.no_diffs and (old_head != pr["headRefOid"] or not diff_path.exists()):
            # newline="" keeps the diff's LF endings on Windows, so it still applies with git
            diff_path.write_text(gh.diff(owner, name, pr["number"]), encoding="utf-8", newline="")
            fetched += 1
        write_json(meta_path, pr)

    write_json(CACHE / "index.json", {
        "repo": args.repo, "label": args.label,
        "issues": {n: by_issue[n] for n in sorted(by_issue)},
    })
    contested = sorted(by_issue.items(), key=lambda kv: -len(kv[1]))
    print(f"{len(issues)} issues, {len(competing)} competing PRs, {fetched} diffs fetched, "
          f"rate limit left: {gh.remaining or 'n/a'}")
    print("most contested:", ", ".join(f"#{n} ({len(p)})" for n, p in contested[:8]))
    print("no PR yet:", sum(1 for p in by_issue.values() if not p))


if __name__ == "__main__":
    main()
