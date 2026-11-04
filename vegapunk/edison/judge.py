"""Pure logic: read pytest junit XML and turn two runs into a verdict."""

import ast
import re
import xml.etree.ElementTree as ET

CORE_TEST_RE = re.compile(r"^core/tests/(?!integration/|benchmarks/|e2e/).*test_[^/]*\.py$|^core/tests/.*_test\.py$")
TS_TEST_RE = re.compile(r"^(console|gateway)/.*\.test\.[cm]?[tj]sx?$")
# what Edison can run offline: Console workspace packages, not the desktop app (Electron/browser)
# and not *.integration tests
TS_RUNNABLE_RE = re.compile(r"^console/packages/([^/]+)/(?!.*\.integration\.test\.).*\.test\.[cm]?[tj]sx?$")


def core_test_module(path: str) -> str:
    """core/tests/a/test_b.py -> tests.a.test_b (pytest's rootdir is core/)."""
    return path.removeprefix("core/").removesuffix(".py").replace("/", ".")


def parse_junit(text: str) -> dict:
    """{'cases': {test id: passed|failed|error|skipped}, 'collect_errors': {module, ...}}"""
    cases, collect_errors = {}, set()
    for case in ET.fromstring(text).iter("testcase"):
        classname, name = case.get("classname", ""), case.get("name", "")
        error = case.find("error")
        if error is not None and "collection failure" in (error.get("message") or ""):
            collect_errors.add(f"{classname}.{name}" if classname else name)
            continue
        if case.find("failure") is not None:
            status = "failed"
        elif error is not None:
            status = "error"
        elif case.find("skipped") is not None:
            status = "skipped"
        else:
            status = "passed"
        cases[f"{classname}::{name}"] = status
    return {"cases": cases, "collect_errors": collect_errors}


ASSERTING_CALL = re.compile(r"assert|raises|expect|fail|verify|check", re.I)


def _asserts(fn: ast.AST) -> bool:
    """True if a test body contains an assert statement or an asserting call (pytest.raises, mock.assert_*, ...)."""
    for node in ast.walk(fn):
        if isinstance(node, ast.Assert):
            return True
        if isinstance(node, ast.Call):
            f = node.func
            name = f.attr if isinstance(f, ast.Attribute) else f.id if isinstance(f, ast.Name) else ""
            if ASSERTING_CALL.search(name):
                return True
        if isinstance(node, (ast.With, ast.AsyncWith)):
            for item in node.items:
                c = item.context_expr
                if isinstance(c, ast.Call):
                    f = c.func
                    name = f.attr if isinstance(f, ast.Attribute) else f.id if isinstance(f, ast.Name) else ""
                    if ASSERTING_CALL.search(name):
                        return True
    return False


def assertion_free(sources: dict[str, str]) -> set[str]:
    """Test ids ('classname::name', no parameters) whose bodies assert nothing.

    A test that asserts nothing can still fail on the base commit (its module does not import
    there), which would let it "prove" a change it never checks. Planted-defect runs showed it.
    Helper calls are not followed, so a test that only calls an asserting helper is flagged too;
    the cost is a conservative proof count, never a false one.
    """
    hollow = set()
    for path, source in sources.items():
        try:
            tree = ast.parse(source)
        except SyntaxError:
            continue
        module = core_test_module(path)
        scopes = [(module, tree.body)] + [(f"{module}.{n.name}", n.body) for n in tree.body
                                          if isinstance(n, ast.ClassDef)]
        for prefix, body in scopes:
            for fn in body:
                if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)) and fn.name.startswith("test") \
                        and not _asserts(fn):
                    hollow.add(f"{prefix}::{fn.name}")
    return hollow


def module_of(test_id: str, modules: list[str]) -> str | None:
    classname = test_id.split("::", 1)[0]
    matches = [m for m in modules if classname == m or classname.startswith(m + ".")]
    return max(matches, key=len) if matches else None


def judge(head: dict | None, base: dict | None, modules: list[str], hollow: set[str] = frozenset()) -> dict:
    """Compare a head run and a base run of the same test files.

    proven: passes on head, fails or is uncollectable on base (the test exercises the change)
    unproven: passes on both (the test does not distinguish the change)
    broken: fails on head
    hollow: would count as proven but asserts nothing, so it proves nothing
    """
    empty = {"proven": 0, "unproven": 0, "broken": 0, "passed": 0, "hollow": 0}
    if not modules:
        return {"verdict": "No tests", **empty}
    if head is None:
        return {"verdict": "Unreproducible", **empty}
    cases = head["cases"]
    broken = sum(s in ("failed", "error") for s in cases.values()) + len(head["collect_errors"])
    passed = [t for t, s in cases.items() if s == "passed"]
    proven = unproven = hollow_count = 0
    for t in passed:
        if base is None:
            continue
        before = base["cases"].get(t)
        if before in ("failed", "error") or module_of(t, modules) in base["collect_errors"]:
            if t.split("[", 1)[0] in hollow:
                hollow_count += 1
            else:
                proven += 1
        elif before == "passed":
            unproven += 1
    if broken:
        verdict = "Broken"
    elif not passed:
        verdict = "No tests ran"
    elif proven:
        verdict = "Proven"
    else:
        verdict = "Unproven"
    return {"verdict": verdict, "proven": proven, "unproven": unproven + hollow_count, "broken": broken,
            "passed": len(passed), "hollow": hollow_count}


def judge_ts(head: dict | None, base: dict | None, files: list[str]) -> dict:
    """Vitest version of judge(): a test missing from the base run counts as failing before,
    because the PR's test file is copied into the base tree and only fails to load when the
    code it tests is not there."""
    if not files:
        return {"verdict": "No tests", "proven": 0, "unproven": 0, "broken": 0, "passed": 0}
    if head is None:
        return {"verdict": "Unreproducible", "proven": 0, "unproven": 0, "broken": 0, "passed": 0}
    broken = sum(s in ("failed", "error") for s in head["cases"].values())
    passed = [t for t, s in head["cases"].items() if s == "passed"]
    base_cases = (base or {}).get("cases", {})
    proven = sum(1 for t in passed if base is not None and base_cases.get(t) != "passed")
    unproven = sum(1 for t in passed if base_cases.get(t) == "passed")
    verdict = "Broken" if broken else "No tests ran" if not passed else "Proven" if proven else "Unproven"
    return {"verdict": verdict, "proven": proven, "unproven": unproven, "broken": broken, "passed": len(passed)}


def merge_verdicts(py: dict, ts: dict | None) -> dict:
    """One verdict for a PR from its Python and TypeScript proofs."""
    if not ts or ts["verdict"] == "No tests":
        return py
    if py["verdict"] == "No tests":
        return ts
    counts = {k: py[k] + ts[k] for k in ("proven", "unproven", "broken", "passed")}
    order = ["Broken", "Proven", "Unproven", "No tests ran", "Unreproducible"]
    verdicts = {py["verdict"], ts["verdict"]}
    return {"verdict": next(v for v in order if v in verdicts), **counts}


def pass_rate(run: dict | None) -> float | None:
    """Share of a run's tests that passed; an uncollectable file counts as a failure."""
    if run is None:
        return None
    statuses = [s for s in run["cases"].values() if s != "skipped"]
    total = len(statuses) + len(run["collect_errors"])
    return round(sum(s == "passed" for s in statuses) / total, 3) if total else None
