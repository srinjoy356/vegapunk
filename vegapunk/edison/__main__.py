"""Edison's sandbox runner. See vegapunk/edison/__init__.py for what it proves."""

import argparse
import hashlib
import json
import shutil
import os
import subprocess
import tempfile
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from vegapunk.edison.judge import (CORE_TEST_RE, TS_TEST_RE, assertion_free, core_test_module, judge,
                                   merge_verdicts, parse_junit, pass_rate)

VERSION = 2  # bump when a change makes cached results incomparable
CACHE = Path("cache")
OUT = CACHE / "edison"
HERE = Path(__file__).parent
REPO = Path(os.environ.get("EDISON_REPO", Path.home() / "vegapunk-work" / "switch"))
RUNS = Path(os.environ.get("EDISON_RUNS", Path.home() / "vegapunk-work" / "runs"))
RUN_TIMEOUT = 20 * 60
PG_IMAGE = "postgres:16-alpine"


def sh(*cmd, cwd=None, check=True, timeout=None) -> str:
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    if check and r.returncode != 0:
        raise RuntimeError(f"{' '.join(map(str, cmd))} failed: {r.stderr.strip()[-2000:]}")
    return r.stdout


def git(*args, check=True) -> str:
    return sh("git", "-C", str(REPO), *args, check=check)


def fetch() -> None:
    git("fetch", "-q", "origin", "+refs/pull/*/head:refs/remotes/pr/*", "+refs/heads/main:refs/remotes/origin/main")


def ref_for(label) -> str:
    """PR numbers live under refs/remotes/pr/; planted variants under refs/vegapunk/."""
    return f"refs/remotes/pr/{label}" if str(label).isdigit() else f"refs/vegapunk/{label}"


def slug(label) -> str:
    return str(label).replace("/", "_")


def changed_files(base: str, head: str) -> list[str]:
    """Files added or modified by the PR (deleted ones cannot be run)."""
    out = git("diff", "--name-only", "--diff-filter=AMR", base, head)
    return [f for f in out.splitlines() if f]


def base_of(head: str) -> str:
    """Where the PR forked from main. For an already-merged PR (head is in main's history),
    the first parent of the merge commit that brought it in."""
    base = git("merge-base", head, "refs/remotes/origin/main").strip()
    if base != head:
        return base
    merges = git("rev-list", "--ancestry-path", "--merges", "--reverse", f"{head}..refs/remotes/origin/main").split()
    if not merges:
        return git("rev-parse", f"{head}^").strip()  # fast-forwarded: best effort, the commit before head
    return git("merge-base", head, f"{merges[0]}^1").strip()


def image_for(sha: str) -> str:
    """The test image for a commit's locked dependencies, built once per lock."""
    files = {p: git("show", f"{sha}:{p}") for p in ("core/pyproject.toml", "core/uv.lock")}
    digest = hashlib.sha256("".join(files.values()).encode() + (HERE / "Dockerfile").read_bytes()).hexdigest()[:12]
    tag = f"vegapunk-edison:{digest}"
    if subprocess.run(["docker", "image", "inspect", tag], capture_output=True).returncode == 0:
        return tag
    with tempfile.TemporaryDirectory() as ctx:
        (Path(ctx) / "core").mkdir()
        for p, text in files.items():
            (Path(ctx) / p).write_text(text, encoding="utf-8")
        (Path(ctx) / "Dockerfile").write_bytes((HERE / "Dockerfile").read_bytes())
        sh("docker", "build", "-q", "-t", tag, ctx, timeout=30 * 60)
    return tag


def image_ts_for(sha: str) -> str:
    """The Console test image for a commit's workspace manifests and lockfile, built once per lock."""
    manifests = [p for p in git("ls-tree", "-r", "--name-only", sha, "console").splitlines()
                 if p.endswith(("package.json", "pnpm-lock.yaml", "pnpm-workspace.yaml", ".npmrc"))
                 and "node_modules" not in p and "/fixtures/" not in p]
    files = {p: git("show", f"{sha}:{p}") for p in manifests}
    dockerfile = (HERE / "Dockerfile.ts").read_bytes()
    digest = hashlib.sha256("".join(f"{k}\n{v}" for k, v in sorted(files.items())).encode() + dockerfile).hexdigest()[:12]
    tag = f"vegapunk-edison-ts:{digest}"
    if subprocess.run(["docker", "image", "inspect", tag], capture_output=True).returncode == 0:
        return tag
    with tempfile.TemporaryDirectory() as ctx:
        for p, text in files.items():
            (Path(ctx) / p).parent.mkdir(parents=True, exist_ok=True)
            (Path(ctx) / p).write_text(text, encoding="utf-8")
        (Path(ctx) / "Dockerfile").write_bytes(dockerfile)
        sh("docker", "build", "-q", "-t", tag, ctx, timeout=60 * 60)
    return tag


TS_SCRIPT = r"""
set -u
cp -a /src/console/. /deps/console/
cd /deps/console
if ! pnpm -r --workspace-concurrency 1 --filter './packages/**' run build > /out/build.log 2>&1; then echo BUILD_FAILED; tail -40 /out/build.log; fi
for pkg in "$@"; do
  files=$(cat /out/files-$pkg)
  (cd packages/$pkg && pnpm exec vitest run --maxWorkers=2 --reporter=junit --outputFile=/out/junit-$pkg.xml $files) > /out/vitest-$pkg.log 2>&1
  tail -15 /out/vitest-$pkg.log
done
"""


def run_ts_tests(tree: Path, image: str, test_files: list[str]) -> tuple[dict | None, str]:
    """Build the PR's Console packages and run its changed vitest files, offline. Returns (junit, log)."""
    from vegapunk.edison.judge import TS_RUNNABLE_RE
    by_pkg: dict[str, list[str]] = {}
    for f in test_files:
        m = TS_RUNNABLE_RE.match(f)
        if m:
            by_pkg.setdefault(m.group(1), []).append(f.split(f"console/packages/{m.group(1)}/", 1)[1])
    if not by_pkg:
        return None, "no runnable Console package tests"
    out = Path(tempfile.mkdtemp(prefix="edison-ts-", dir=RUNS))
    out.chmod(0o777)
    for pkg, files in by_pkg.items():
        (out / f"files-{pkg}").write_text(" ".join(files), encoding="utf-8")
    cmd = ["docker", "run", "--rm", "--network", "none", "--memory", "4g", "--cpus", "2", "--pids-limit", "2048",
           "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
           "-v", f"{tree}:/src:ro", "-v", f"{out}:/out", "-e", "CI=1",
           image, "bash", "-c", TS_SCRIPT, "edison-ts", *by_pkg]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=RUN_TIMEOUT)
        log = (r.stdout + r.stderr)[-4000:]
    except subprocess.TimeoutExpired:
        return None, f"timed out after {RUN_TIMEOUT}s"
    merged = {"cases": {}, "collect_errors": set()}
    found = False
    for pkg in by_pkg:
        junit = out / f"junit-{pkg}.xml"
        if junit.exists():
            found = True
            run = parse_junit(junit.read_text(encoding="utf-8"))
            merged["cases"].update({f"{pkg}/{k}": v for k, v in run["cases"].items()})
    shutil.rmtree(out, ignore_errors=True)
    return (merged if found else None), log


def prove_ts(result: dict) -> dict:
    """Add the TypeScript proof to a PR's result (head run + base run of its changed vitest files)."""
    from vegapunk.edison.judge import TS_RUNNABLE_RE, judge_ts
    files = [f for f in result.get("ts_tests_not_run", []) if TS_RUNNABLE_RE.match(f)]
    if not files:
        result["ts"] = {"verdict": "No tests", "files": []}
        return result
    # infrastructure failures (image build, checkout) propagate: with_ts() then leaves the result
    # without a TS proof so a later run retries, instead of caching "Unreproducible"
    image = image_ts_for(result["head"])
    with Worktree(result["head"]) as tree:
        head_run, head_log = run_ts_tests(tree, image, files)
    with Worktree(result["base"], overlay_from=result["head"], overlay=files) as tree:
        base_run, base_log = run_ts_tests(tree, image, files)
    result["ts"] = {**judge_ts(head_run, base_run, files), "files": files,
                    "head_run": serializable(head_run), "base_run": serializable(base_run),
                    "head_log": head_log, "base_log": base_log}
    return result


class Worktree:
    """A throwaway checkout of `sha`, optionally with files copied in from another commit."""

    def __init__(self, sha: str, overlay_from: str | None = None, overlay: list[str] = ()):
        self.path = RUNS / uuid.uuid4().hex[:12]
        self.sha, self.overlay_from, self.overlay = sha, overlay_from, list(overlay)

    def __enter__(self) -> Path:
        RUNS.mkdir(parents=True, exist_ok=True)
        git("worktree", "add", "-q", "--detach", str(self.path), self.sha)
        if self.overlay_from and self.overlay:
            sh("git", "-C", str(self.path), "checkout", self.overlay_from, "--", *self.overlay)
        return self.path

    def __exit__(self, *exc):
        git("worktree", "remove", "--force", str(self.path), check=False)


def run_tests(tree: Path, image: str, test_files: list[str]) -> tuple[dict | None, str]:
    """Run test files in a no-internet container beside a throwaway Postgres. Returns (junit, log)."""
    rid = uuid.uuid4().hex[:10]
    net, pg = f"edison-{rid}", f"edison-pg-{rid}"
    (tree / ".edison").mkdir(exist_ok=True)
    junit = tree / ".edison" / "junit.xml"
    try:
        sh("docker", "network", "create", "--internal", net)
        sh("docker", "run", "-d", "--name", pg, "--network", net, "--tmpfs", "/var/lib/postgresql/data",
           "-e", "POSTGRES_USER=edison", "-e", "POSTGRES_PASSWORD=edison", "-e", "POSTGRES_DB=edison",
           PG_IMAGE, "postgres", "-c", "fsync=off", "-c", "synchronous_commit=off", "-c", "full_page_writes=off")
        for _ in range(60):
            if subprocess.run(["docker", "exec", pg, "pg_isready", "-U", "edison"], capture_output=True).returncode == 0:
                break
            time.sleep(1)
        cmd = [
            "docker", "run", "--rm", "--name", f"edison-run-{rid}", "--network", net,
            "--memory", "3g", "--cpus", "2", "--pids-limit", "1024",
            "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
            "--read-only", "--tmpfs", "/tmp:exec",
            "-v", f"{tree}:/src", "-v", f"{HERE}:/edison:ro",
            "-e", "PYTHONPATH=/edison:/src/core", "-e", "HOME=/tmp", "-e", f"EDISON_PG_HOST={pg}",
            image, "python", "-m", "pytest", "-c", "core/pyproject.toml", "-p", "pg_redirect",
            # no --timeout: older branches lock deps without pytest-timeout; RUN_TIMEOUT bounds the run instead
            "-p", "no:cacheprovider", "-q", "--junitxml=/src/.edison/junit.xml",
            # a base tree can't import the PR's new modules; still run the files that do import
            "--continue-on-collection-errors", *test_files,
        ]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=RUN_TIMEOUT)
            log = (r.stdout + r.stderr)[-4000:]
        except subprocess.TimeoutExpired:
            subprocess.run(["docker", "kill", f"edison-run-{rid}"], capture_output=True)
            log = f"timed out after {RUN_TIMEOUT}s"
        parsed = parse_junit(junit.read_text(encoding="utf-8")) if junit.exists() else None
        return parsed, log
    finally:
        subprocess.run(["docker", "rm", "-f", pg], capture_output=True)
        subprocess.run(["docker", "network", "rm", net], capture_output=True)


def serializable(run: dict | None) -> dict | None:
    return None if run is None else {"cases": run["cases"], "collect_errors": sorted(run["collect_errors"])}


def loaded(run: dict | None) -> dict | None:
    return None if run is None else {"cases": run["cases"], "collect_errors": set(run["collect_errors"])}


def with_ts(result: dict, out_path: Path) -> dict:
    """Run the TypeScript proof once for a result that lacks it, and fold it into the PR's verdict."""
    if "ts" in result or not result.get("ts_tests_not_run"):
        return result
    keys = ("verdict", "proven", "unproven", "broken", "passed")
    py = result.get("py") or {k: result[k] for k in keys}
    started = time.time()
    try:
        prove_ts(result)
    except Exception as e:
        print(f"PR #{result['pr']} TS: sandbox error, will retry next run: {str(e)[-300:]}", flush=True)
        return result
    result["py"] = py
    result.update(merge_verdicts(py, result["ts"]))
    out_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"PR #{result['pr']} TS: {result['ts']['verdict']} (proven {result['ts'].get('proven', 0)}) "
          f"-> overall {result['verdict']} in {round(time.time() - started)}s", flush=True)
    return result


def resolve_base(label, head: str) -> str:
    """A planted variant is judged against its original PR's base, recorded when it was made."""
    if not str(label).isdigit():
        recorded = git("rev-parse", "--verify", "-q", f"refs/vegapunk/base/{label}", check=False).strip()
        if recorded:
            return recorded
    return base_of(head)


def hollow_of(head: str, core_tests: list[str]) -> set[str]:
    return assertion_free({f: git("show", f"{head}:{f}") for f in core_tests})


def rejudge(cached: dict, out_path: Path) -> dict:
    """Apply the assertion check to a result cached before it existed, from its stored runs: no rerun."""
    modules = [core_test_module(f) for f in cached["core_tests"]]
    py = judge(loaded(cached["head_run"]), loaded(cached["base_run"]), modules, hollow_of(cached["head"], cached["core_tests"]))
    if "py" in cached:
        cached["py"] = py
        cached.update(merge_verdicts(py, cached.get("ts")))
    else:
        cached.update(py)
    cached["hollow"] = py["hollow"]
    out_path.write_text(json.dumps(cached, indent=2), encoding="utf-8")
    return cached


def prove(pr_number, force: bool = False, ts: bool = False) -> dict:
    """Head run + base run of the PR's own core tests -> verdict. Cached per head/base.
    ts: also prove its changed Console vitest files (added to a cached result without rerunning Python)."""
    head = git("rev-parse", ref_for(pr_number)).strip()
    base = resolve_base(pr_number, head)
    out_path = OUT / f"pr-{slug(pr_number)}.json"
    if out_path.exists() and not force:
        cached = json.loads(out_path.read_text(encoding="utf-8"))
        if (cached.get("head"), cached.get("base"), cached.get("version")) == (head, base, VERSION):
            if "hollow" not in cached and cached.get("core_tests") and cached.get("head_run"):
                cached = rejudge(cached, out_path)
            return with_ts(cached, out_path) if ts else cached
    files = changed_files(base, head)
    core_tests = [f for f in files if CORE_TEST_RE.match(f)]
    ts_tests = [f for f in files if TS_TEST_RE.match(f)]
    modules = [core_test_module(f) for f in core_tests]
    result = {"version": VERSION, "pr": pr_number, "head": head, "base": base,
              "core_tests": core_tests, "ts_tests_not_run": ts_tests,
              "deps_changed": any(f in files for f in ("core/uv.lock", "core/pyproject.toml"))}
    started = time.time()
    head_run = base_run = None
    head_log = base_log = ""
    if core_tests:
        try:
            image = image_for(head)
            with Worktree(head) as tree:
                head_run, head_log = run_tests(tree, image, core_tests)
            with Worktree(base, overlay_from=head, overlay=core_tests) as tree:
                base_run, base_log = run_tests(tree, image, core_tests)
        except Exception as e:  # build or checkout failure: report it, don't crash the batch
            head_log = f"sandbox error: {e}"
    result.update(judge(head_run, base_run, modules, hollow_of(head, core_tests) if core_tests else set()))
    result.update({"head_run": serializable(head_run), "base_run": serializable(base_run),
                   "head_log": head_log, "base_log": base_log, "seconds": round(time.time() - started)})
    OUT.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"PR #{pr_number}: {result['verdict']} (proven {result['proven']}, unproven {result['unproven']}, "
          f"broken {result['broken']}) in {result['seconds']}s", flush=True)
    return with_ts(result, out_path) if ts else result


ATLAS_SCRIPT = r"""
import json, subprocess, sys
files = sys.argv[1:]
def count(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr
out = {}
code, text = count(["ruff", "check", "--quiet", "--output-format", "concise", *files])
out["ruff"] = sum(1 for l in text.splitlines() if ":" in l and l.split(":")[0].endswith(".py"))
code, text = count(["ruff", "format", "--check", "--quiet", *files])
out["format"] = sum(1 for l in text.splitlines() if l.startswith("Would reformat"))
src = [f for f in files if f.startswith("core/switch_core/")]
if src:
    code, text = count(["mypy", "--config-file", "core/pyproject.toml", "--follow-imports", "silent",
                        "--no-error-summary", *src])
    out["mypy"] = sum(1 for l in text.splitlines() if ": error:" in l)
else:
    out["mypy"] = 0
print("ATLAS" + json.dumps(out))
"""


def static_checks(tree: Path, image: str, files: list[str]) -> dict | None:
    """ruff, ruff format and mypy error counts for `files` in an offline container."""
    files = [f for f in files if (tree / f).exists()]
    if not files:
        return {"ruff": 0, "format": 0, "mypy": 0}
    cmd = ["docker", "run", "--rm", "--network", "none", "--memory", "3g", "--cpus", "2",
           "--cap-drop", "ALL", "--security-opt", "no-new-privileges", "--read-only", "--tmpfs", "/tmp:exec",
           "-v", f"{tree}:/src:ro", "-e", "HOME=/tmp", "-e", "MYPY_CACHE_DIR=/tmp/mypy", "-e", "RUFF_CACHE_DIR=/tmp/ruff",
           "-w", "/src/core", image, "python", "-c", ATLAS_SCRIPT, *[f.removeprefix("core/") for f in files]]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=RUN_TIMEOUT)
    except subprocess.TimeoutExpired:
        return None
    line = next((l for l in r.stdout.splitlines() if l.startswith("ATLAS")), None)
    return json.loads(line[5:]) if line else None


def atlas(pr_number, force: bool = False) -> dict:
    """Atlas: lint, format and type errors the PR adds to the core files it touches (head minus base)."""
    head = git("rev-parse", ref_for(pr_number)).strip()
    base = resolve_base(pr_number, head)
    out_path = CACHE / "atlas" / f"pr-{slug(pr_number)}.json"
    if out_path.exists() and not force:
        cached = json.loads(out_path.read_text(encoding="utf-8"))
        if (cached.get("head"), cached.get("base"), cached.get("version")) == (head, base, VERSION):
            return cached
    files = [f for f in changed_files(base, head) if f.startswith("core/") and f.endswith(".py")]
    result = {"version": VERSION, "pr": pr_number, "head": head, "base": base, "files": files}
    if files:
        image = image_for(head)
        with Worktree(head) as tree:
            after = static_checks(tree, image, files)
        with Worktree(base) as tree:
            before = static_checks(tree, image, files)
        result["head_counts"], result["base_counts"] = after, before
        if after is not None and before is not None:
            result["added"] = {k: max(0, after[k] - before[k]) for k in after}
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"Atlas PR #{pr_number}: {result.get('added', 'n/a')}", flush=True)
    return result


def cross(code_pr: dict, tests_pr: dict) -> float | None:
    """Pass rate of tests_pr's core tests run against code_pr's head."""
    if not tests_pr["core_tests"]:
        return None
    image = image_for(code_pr["head"])
    with Worktree(code_pr["head"], overlay_from=tests_pr["head"], overlay=tests_pr["core_tests"]) as tree:
        run, _ = run_tests(tree, image, tests_pr["core_tests"])
    return pass_rate(run)


def matrix(issue: int, prs: list[dict], jobs: int) -> dict:
    """matrix[code][tests] = pass rate of `tests` PR's tests on `code` PR's head; cached per head pair."""
    path = OUT / f"matrix-{issue}.json"
    old = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    heads = {str(p["pr"]): p["head"] for p in prs}
    pairs = [(a, b) for a in prs for b in prs if a is not b]
    cells: dict[str, dict] = {str(p["pr"]): {} for p in prs}

    def cell(pair):
        a, b = pair
        prev = old.get("cells", {}).get(str(a["pr"]), {}).get(str(b["pr"]))
        # reuse only real results: a None cell (sandbox failure) is worth retrying
        if prev and prev.get("rate") is not None and prev.get("heads") == [a["head"], b["head"]] \
                and old.get("version") == VERSION:
            return a, b, prev["rate"]
        try:
            return a, b, cross(a, b)
        except Exception as e:
            print(f"matrix #{issue} {a['pr']}<-{b['pr']}: {e}", flush=True)
            return a, b, None

    with ThreadPoolExecutor(jobs) as pool:
        for a, b, rate in pool.map(cell, pairs):
            cells[str(a["pr"])][str(b["pr"])] = {"rate": rate, "heads": [a["head"], b["head"]]}
    result = {"version": VERSION, "issue": issue, "heads": heads, "cells": cells}
    path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"matrix #{issue}: {len(pairs)} cells", flush=True)
    return result


def main() -> None:
    ap = argparse.ArgumentParser(description="Edison: fail-before/pass-after proofs for competing PRs")
    target = ap.add_mutually_exclusive_group(required=True)
    target.add_argument("--issue", type=int, action="append", help="issue number (repeatable)")
    target.add_argument("--pr", type=int, action="append", help="single PR number (repeatable)")
    target.add_argument("--all", action="store_true", help="every issue in cache/index.json")
    target.add_argument("--prs-file", help="JSON file with a 'prs' object keyed by PR number (the backtest sample)")
    ap.add_argument("--matrix", action="store_true", help="also run each rival's tests on each PR")
    ap.add_argument("--atlas", action="store_true", help="also run Atlas's lint/format/type checks")
    ap.add_argument("--ts", action="store_true", help="also prove changed Console vitest files")
    ap.add_argument("--jobs", type=int, default=1)
    ap.add_argument("--force", action="store_true", help="ignore cached results")
    ap.add_argument("--no-fetch", action="store_true")
    args = ap.parse_args()

    if not args.no_fetch:
        fetch()
    sh("docker", "pull", "-q", PG_IMAGE)
    def checks(n: int) -> dict:
        if args.atlas:
            try:
                atlas(n, args.force)
            except Exception as e:  # Atlas is advisory; never lose Edison's proof over it
                print(f"Atlas PR #{n}: {e}", flush=True)
        return prove(n, args.force, args.ts)

    if args.prs_file:
        args.pr = [int(n) for n in json.loads(Path(args.prs_file).read_text(encoding="utf-8"))["prs"]]
    if args.pr:
        with ThreadPoolExecutor(args.jobs) as pool:
            list(pool.map(checks, args.pr))
        return
    index = json.loads((CACHE / "index.json").read_text(encoding="utf-8"))["issues"]
    issues = sorted(map(int, index)) if args.all else args.issue
    for issue in issues:
        numbers = index.get(str(issue), [])
        if not numbers:
            continue
        with ThreadPoolExecutor(args.jobs) as pool:
            proofs = list(pool.map(checks, numbers))
        if args.matrix and len(proofs) > 1:
            matrix(issue, proofs, args.jobs)


if __name__ == "__main__":
    main()
