import json

import pytest

from vegapunk import york
from vegapunk.pythagoras import compare
from vegapunk.rank import combine, cross_signal, edison_signal, high_flags
from vegapunk.switch import parse_sse
from vegapunk.tribunal import PICK_RE, normalize, parse_verdict


def test_edison_signal_rewards_share_of_proving_tests():
    assert edison_signal({"verdict": "Proven", "proven": 10, "passed": 10}) == 1.0
    assert edison_signal({"verdict": "Proven", "proven": 0, "passed": 10}) == 0.7
    assert edison_signal({"verdict": "Broken"}) == 0.0
    assert edison_signal(None) is None


def test_combine_reweights_missing_signals():
    assert combine({"edison": 1.0, "cross": None, "spec": None, "safety": None, "atlas": None}) == 1.0
    assert combine({"edison": 1.0, "spec": 0.0, "cross": None, "safety": None, "atlas": None}) == pytest.approx(0.5)
    assert combine({"edison": None}) is None


def test_cross_signal_averages_known_rates():
    m = {"cells": {"1": {"2": {"rate": 1.0}, "3": {"rate": 0.5}, "4": {"rate": None}}}}
    assert cross_signal(m, "1") == 0.75
    assert cross_signal(m, "9") is None


def test_high_flags_only_high_or_critical():
    v = {"lilith": {"flags": {"7": ["high: leaks token", "low: naming", {"severity": "critical", "issue": "rce"}]}}}
    assert high_flags(v, "7") == ["high: leaks token", "critical: rce"]


def test_parse_verdict_and_normalize_drop_foreign_prs():
    text = 'thoughts\n```verdict\n{"satellite": "shaka", "ranking": ["#2", 1, 99], "scores": {"1": 6, "#2": 9, "99": 10}}\n```'
    v = normalize(parse_verdict(text), [1, 2])
    assert v["ranking"] == [2, 1] and v["scores"] == {"1": 6.0, "2": 9.0}
    flagged = normalize({"scores": {}, "flags": {"#2": ["high: x"]}, "notes": {"#1": "ok"}}, [1, 2])
    assert flagged["flags"] == {"2": ["high: x"]} and flagged["notes"] == {"1": "ok"}
    assert parse_verdict("no block here") is None
    assert parse_verdict("```verdict\n{not json}\n```") is None


def test_pick_command():
    m = PICK_RE.search("ok, pick #1215 because it follows the opt-in direction")
    assert m and m.group(1) == "1215" and m.group(2).startswith("because")
    assert PICK_RE.search("no decision yet") is None


def test_parse_sse_frames_skip_keepalives():
    lines = [": keepalive", "id: 5", "event: message", 'data: {"a":', "data: 1}", "", "event: gap", "data: {}", ""]
    frames = list(parse_sse(lines))
    assert frames[0] == {"id": "5", "event": "message", "data": '{"a":\n1}'}
    assert json.loads(frames[0]["data"]) == {"a": 1}
    assert frames[1] == {"event": "gap", "data": "{}"}


def test_york_refuses_past_cap(tmp_path, monkeypatch):
    ledger = tmp_path / "ledger.jsonl"
    ledger.write_text(json.dumps({"usd": 0.9999, "purpose": "x", "prompt_tokens": 1, "completion_tokens": 1}) + "\n")
    monkeypatch.setenv("YORK_CAP_USD", "1.00")
    monkeypatch.setenv("OPENAI_API_KEY", "unused")
    with pytest.raises(york.CapReached):
        york.chat([{"role": "user", "content": "x" * 3000}], purpose="test", ledger=ledger)
    assert york.cost("gpt-4o-mini", 1_000_000, 1_000_000) == pytest.approx(0.75)


def test_pythagoras_flags_later_copy_only():
    shared = "\n".join(f"+line number {i} of the shared implementation" for i in range(20))
    prs = [{"number": 1, "createdAt": "2026-11-01", "additions": 20, "deletions": 0},
           {"number": 2, "createdAt": "2026-11-02", "additions": 20, "deletions": 0}]
    diffs = {1: "diff --git a/x.py b/x.py\n" + shared, 2: "diff --git a/y.py b/y.py\n" + shared}
    out = compare(prs, diffs)
    assert out[2]["copied_from"] == 1 and out[1]["copied_from"] is None
    assert out[1]["files"] == ["x.py"]


def test_planted_mutations_keep_helpers_and_empty_tests():
    from vegapunk.planted import hollow, skip
    src = "def helper():\n    return 1\n\ndef test_a():\n    assert helper() == 2\n"
    out = hollow(src)
    assert "return 1" in out and "assert helper() == 2" not in out
    assert skip("x = 1").startswith("import pytest\npytestmark = pytest.mark.skip(")


def test_backtest_auc_and_decided():
    from vegapunk.backtest import auc, decided
    assert auc([(1.0, True), (0.0, False)]) == 1.0
    assert auc([(0.5, True), (0.5, False)]) == 0.5
    assert auc([(1.0, True)]) is None
    pr = lambda n, merged, state, issue: {"number": n, "merged": merged, "state": state, "createdAt": str(n),
                                          "body": f"Closes #{issue}", "closingIssuesReferences": {"nodes": []}}
    prs = [pr(1, True, "MERGED", 10), pr(2, False, "CLOSED", 10), pr(3, False, "OPEN", 11), pr(4, True, "MERGED", 11)]
    assert list(decided(prs)) == [10]


def test_seal_hash_is_stable_and_reveal_detects_tampering(tmp_path, monkeypatch):
    import hashlib
    from vegapunk import seal
    monkeypatch.chdir(tmp_path)
    payload = {"sealed_at": "S", "issues": [{"issue": 1, "ranking": [2, 3]}]}
    body = seal.canonical(payload)
    assert body == seal.canonical(json.loads(body))  # key order and spacing can't change the hash
    (tmp_path / "predictions").mkdir()
    (tmp_path / "predictions" / "S.sha256").write_text(hashlib.sha256(body).hexdigest() + "  rankings-S.json\n")
    tampered = tmp_path / "r.json"
    tampered.write_bytes(seal.canonical({**payload, "issues": [{"issue": 1, "ranking": [3, 2]}]}))
    with pytest.raises(SystemExit, match="hash mismatch"):
        seal.reveal(tampered)


def test_split_diff_respects_size_files_and_drops_lockfiles():
    from vegapunk.tribunal import split_diff
    f = lambda name, n: f"diff --git a/{name} b/{name}\n" + "".join(f"+line {i}\n" for i in range(n))
    diff = f("a.py", 10) + f("uv.lock", 500) + f("b.py", 10) + f("big.py", 3000)
    parts = split_diff(diff, size=2000)
    assert all(len(p) <= 2000 for p in parts)
    joined = "".join(parts)
    assert "uv.lock" not in joined and "a/a.py" in joined and "a/big.py" in joined
    assert parts[0].startswith("diff --git a/a.py")
