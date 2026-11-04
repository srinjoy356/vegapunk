from vegapunk.edison.judge import CORE_TEST_RE, TS_TEST_RE, core_test_module, judge, parse_junit, pass_rate

MOD = "tests.switch_core.test_redact"


def junit(*cases: str) -> str:
    return f"<testsuites><testsuite>{''.join(cases)}</testsuite></testsuites>"


def case(name, child="", classname=MOD):
    return f'<testcase classname="{classname}" name="{name}">{child}</testcase>'


HEAD = parse_junit(junit(case("test_new"), case("test_old"), case("test_skip", "<skipped/>")))


def test_parse_junit_statuses_and_collection_errors():
    run = parse_junit(junit(
        case("test_a"), case("test_b", "<failure/>"), case("test_c", "<error message='boom'/>"),
        case(MOD, "<error message='collection failure'/>", classname=""),
    ))
    assert run["cases"] == {f"{MOD}::test_a": "passed", f"{MOD}::test_b": "failed", f"{MOD}::test_c": "error"}
    assert run["collect_errors"] == {MOD}


def test_new_test_failing_on_base_proves_the_change():
    base = parse_junit(junit(case("test_new", "<failure/>"), case("test_old")))
    r = judge(HEAD, base, [MOD])
    assert (r["verdict"], r["proven"], r["unproven"]) == ("Proven", 1, 1)


def test_uncollectable_on_base_counts_as_failing_before():
    base = parse_junit(junit(case(MOD, "<error message='collection failure'/>", classname="")))
    assert judge(HEAD, base, [MOD])["proven"] == 2


def test_class_based_tests_map_to_their_module():
    head = parse_junit(junit(case("test_x", classname=f"{MOD}.TestRedact")))
    base = parse_junit(junit(case(MOD, "<error message='collection failure'/>", classname="")))
    assert judge(head, base, [MOD])["verdict"] == "Proven"


def test_tests_passing_on_both_are_unproven():
    assert judge(HEAD, HEAD, [MOD])["verdict"] == "Unproven"


def test_failure_on_head_is_broken_and_missing_run_is_unreproducible():
    head = parse_junit(junit(case("test_new", "<failure/>")))
    assert judge(head, None, [MOD])["verdict"] == "Broken"
    assert judge(None, None, [MOD])["verdict"] == "Unreproducible"
    assert judge(None, None, [])["verdict"] == "No tests"


def test_pass_rate_ignores_skips_and_counts_collection_errors():
    assert pass_rate(HEAD) == 1.0
    run = parse_junit(junit(case("test_a"), case("other", "<error message='collection failure'/>", classname="")))
    assert pass_rate(run) == 0.5
    assert pass_rate(None) is None


def test_path_patterns():
    assert CORE_TEST_RE.match("core/tests/switch_core/test_redact.py")
    assert not CORE_TEST_RE.match("core/tests/integration/test_slow.py")
    assert not CORE_TEST_RE.match("core/switch_core/redact.py")
    assert TS_TEST_RE.match("console/packages/shared/src/x.test.ts")
    assert core_test_module("core/tests/switch_core/test_redact.py") == MOD


def test_ts_judge_and_merge():
    from vegapunk.edison.judge import TS_RUNNABLE_RE, judge_ts, merge_verdicts
    head = {"cases": {"a::x": "passed", "a::y": "passed"}, "collect_errors": set()}
    base = {"cases": {"a::y": "passed"}, "collect_errors": set()}
    r = judge_ts(head, base, ["f"])
    assert (r["verdict"], r["proven"], r["unproven"]) == ("Proven", 1, 1)
    py = {"verdict": "Unproven", "proven": 0, "unproven": 3, "broken": 0, "passed": 3}
    assert merge_verdicts(py, r)["verdict"] == "Proven" and merge_verdicts(py, r)["passed"] == 5
    assert merge_verdicts(py, {**r, "verdict": "Broken"})["verdict"] == "Broken"
    assert merge_verdicts({**py, "verdict": "No tests"}, r) == r
    assert TS_RUNNABLE_RE.match("console/packages/shared/src/x.test.ts")
    assert not TS_RUNNABLE_RE.match("console/packages/shared/src/x.integration.test.ts")
    assert not TS_RUNNABLE_RE.match("console/apps/switch-console-desktop/src/x.test.ts")


def test_assertion_free_tests_cannot_prove():
    from vegapunk.edison.judge import assertion_free
    src = ("import pytest\nfrom app import thing\n\ndef test_real():\n    assert thing() == 1\n\n"
           "def test_raises():\n    with pytest.raises(ValueError):\n        thing(-1)\n\n"
           "def test_hollow():\n    thing()\n\nclass TestX:\n    def test_mock(self, m):\n        m.assert_called_once()\n"
           "    def test_empty(self):\n        pass\n")
    path = "core/tests/switch_core/test_redact.py"
    hollow = assertion_free({path: src})
    assert hollow == {f"{MOD}::test_hollow", f"{MOD}.TestX::test_empty"}
    head = parse_junit(junit(case("test_real"), case("test_hollow"), case("test_empty", classname=f"{MOD}.TestX")))
    base = parse_junit(junit(case(MOD, "<error message='collection failure'/>", classname="")))
    r = judge(head, base, [MOD], hollow)
    assert (r["proven"], r["hollow"], r["verdict"]) == (1, 2, "Proven")
    only_hollow = parse_junit(junit(case("test_hollow[a]")))
    assert judge(only_hollow, base, [MOD], hollow)["verdict"] == "Unproven"


def test_planted_skip_goes_after_future_imports():
    from vegapunk.planted import skip
    out = skip('"""doc"""\nfrom __future__ import annotations\n\nimport os\n')
    compile(out, "x.py", "exec")
    assert out.index("pytestmark") > out.index("__future__")
