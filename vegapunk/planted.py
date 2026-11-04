"""Planted defects: plant known faults into proven PRs and check that Vegapunk catches them.

Runs on the WSL host, like Edison:

    uv run python -m vegapunk.planted 1215 1387 1154      # make variants, prove them, score detection

Variants (each a commit under refs/vegapunk/planted/<pr>-<kind>):
  revert-impl  the PR's tests, without its implementation      -> Edison must not say Proven
  hollow       every test body replaced with `pass`            -> Edison must say Unproven (passes either way)
  skip         every changed test file marked skip              -> Edison must say "No tests ran"
  secret       a fake AWS key and GitHub token added to a source file -> for Lilith (needs a tribunal);
               Edison is expected to miss it, which is the point of having Lilith
"""

import ast
import json
import sys
import uuid
from pathlib import Path

from vegapunk.edison.__main__ import CACHE, REPO, RUNS, base_of, changed_files, git, prove, sh
from vegapunk.edison.judge import CORE_TEST_RE

KINDS = ("revert-impl", "hollow", "skip", "secret")
EXPECT = {"revert-impl": lambda v: v != "Proven", "hollow": lambda v: v == "Unproven",
          "skip": lambda v: v == "No tests ran", "secret": lambda v: True}
# obviously fake values in the shapes scanners look for
FAKE_SECRET = '\n_PLANTED_AWS_KEY = "AKIAVEGAPUNKPLANTED0"\n_PLANTED_GH_TOKEN = "ghp_vegapunkPlantedFakeToken0000000000000"\n'


def hollow(source: str) -> str:
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test"):
            node.body = [ast.Pass()]
    return ast.unparse(tree)


def skip(source: str) -> str:
    """Mark the whole module skipped, after its docstring and `from __future__` imports (which must come first)."""
    lines = source.splitlines(keepends=True)
    after = 0
    for node in ast.parse(source).body:
        is_doc = isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str)
        if is_doc or (isinstance(node, ast.ImportFrom) and node.module == "__future__"):
            after = node.end_lineno
        else:
            break
    marker = 'import pytest\npytestmark = pytest.mark.skip(reason="vegapunk planted")\n'
    return "".join(lines[:after]) + marker + "".join(lines[after:])


def make(pr: int, kind: str) -> str:
    """Create the variant commit and return its label for Edison."""
    head = git("rev-parse", f"refs/remotes/pr/{pr}").strip()
    base = base_of(head)
    files = changed_files(base, head)
    tests = [f for f in files if CORE_TEST_RE.match(f)]
    impl = [f for f in files if f.startswith("core/switch_core/") and f.endswith(".py")]
    wt = RUNS / f"plant-{uuid.uuid4().hex[:8]}"
    git("worktree", "add", "-q", "--detach", str(wt), head)
    try:
        if kind == "revert-impl":
            added = git("diff", "--name-only", "--diff-filter=A", base, head).split()
            for f in impl:
                if f in added:
                    (wt / f).unlink()
                else:
                    sh("git", "-C", str(wt), "checkout", base, "--", f)
        elif kind in ("hollow", "skip"):
            for f in tests:
                p = wt / f
                p.write_text((hollow if kind == "hollow" else skip)(p.read_text(encoding="utf-8")), encoding="utf-8")
        elif kind == "secret":
            target = wt / (impl[0] if impl else tests[0])
            target.write_text(target.read_text(encoding="utf-8") + FAKE_SECRET, encoding="utf-8")
        sh("git", "-C", str(wt), "add", "-A")
        sh("git", "-C", str(wt), "-c", "user.name=vegapunk", "-c", "user.email=vegapunk@localhost",
           "commit", "-q", "-m", f"vegapunk planted {kind} on #{pr}")
        label = f"planted/{pr}-{kind}"
        git("update-ref", f"refs/vegapunk/{label}", sh("git", "-C", str(wt), "rev-parse", "HEAD").strip())
        git("update-ref", f"refs/vegapunk/base/{label}", base)  # judge against the original PR's base
        return label
    finally:
        git("worktree", "remove", "--force", str(wt), check=False)


def main() -> None:
    prs = [int(a) for a in sys.argv[1:]]
    out_path = CACHE / "planted" / "results.json"
    results = json.loads(out_path.read_text(encoding="utf-8")) if out_path.exists() else {}
    for pr in prs:
        original = prove(pr)
        if original["verdict"] != "Proven":
            print(f"#{pr} is {original['verdict']}, not Proven; skipping (variants need a proven baseline)")
            continue
        for kind in KINDS:
            label = make(pr, kind)
            r = prove(label, force=True)
            results[label] = {"pr": pr, "kind": kind, "verdict": r["verdict"], "proven": r["proven"],
                              "caught_by_edison": EXPECT[kind](r["verdict"]) if kind != "secret" else None}
            print(f"{label}: {r['verdict']}", flush=True)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    scored = [v for v in results.values() if v["caught_by_edison"] is not None]
    by_kind = {}
    for v in scored:
        k = by_kind.setdefault(v["kind"], [0, 0])
        k[0] += v["caught_by_edison"]
        k[1] += 1
    print("Edison detection:", {k: f"{a}/{b}" for k, (a, b) in by_kind.items()})


if __name__ == "__main__":
    main()
