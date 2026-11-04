"""Punk Records: opens a tribunal room per issue, briefs the satellites, collects verdicts, keeps the docket.

    uv run python -m vegapunk.tribunal open 803          # case file + room + kickoff
    uv run python -m vegapunk.tribunal collect 803       # read verdicts from the room, rank, post result
    uv run python -m vegapunk.tribunal run 803           # open, wait for verdicts, finish
    uv run python -m vegapunk.tribunal watch             # live: verdicts and Stella's picks from the event stream
    uv run python -m vegapunk.tribunal docket            # post the ranked docket for every issue

Stella (the human) decides: replying `pick #1215 because ...` in a tribunal room records the
decision, and Punk Records remembers the reason for every later case file.
"""

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

from vegapunk.github import load_env
from vegapunk.rank import rank_issue
from vegapunk.switch import Agent

CACHE = Path("cache")
HERE = Path(__file__).parent
SATELLITES = ("shaka", "lilith")
VERDICT_RE = re.compile(r"```verdict\s*(\{.*?\})\s*```", re.S)
PICK_RE = re.compile(r"\bpick\s+#?(\d+)\b[\s:,-]*(.*)", re.I | re.S)
MAX_POST = 1800  # Discord's 2000-character limit, with room for Switch's own framing


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def _save(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def satellite(name: str) -> dict:
    load_env()
    key = name.upper()
    return {"name": name, "agent": os.environ[f"SATELLITE_{key}_AGENT"],
            "workspace": Path(os.environ[f"SATELLITE_{key}_WORKSPACE"])}


def bridge_for(agent: Agent, kind: str) -> tuple[str, list[str]]:
    """(bridge id, Stella's usernames there) for 'discord' | 'slack' | 'mattermost'."""
    bridges = {b["type"]: b["id"] for b in agent.op("list_bridges")}
    user = os.environ.get(f"STELLA_{kind.upper()}")
    return bridges[kind], [user] if user else []


# Case file ----------------------------------------------------------------

def conventions() -> str:
    """What Stella has decided before, and why: Punk Records' memory across tribunals."""
    decisions = _load(CACHE / "decisions.json") or {}
    lines = [f"- Issue #{i}: picked #{d['pick']}" + (f" because {d['reason']}" if d.get("reason") else "")
             for i, d in sorted(decisions.items(), key=lambda kv: int(kv[0]))]
    return "\n".join(lines[-15:]) or "- (no decisions recorded yet)"


def case_file(issue_number: int) -> str:
    issue = _load(CACHE / "issues" / f"{issue_number}.json")
    pyth = _load(CACHE / "pythagoras" / f"issue-{issue_number}.json") or {"prs": {}, "summaries": {}}
    matrix = _load(CACHE / "edison" / f"matrix-{issue_number}.json")
    out = [f"# Tribunal: issue #{issue_number} — {issue['title']}", "", issue["url"], "",
           "## The issue", "", (issue["body"] or "").strip(), "", "## Maintainer direction (overrides the issue text)", ""]
    for c in issue["maintainer_comments"]:
        out += [f"**{c['author']}** ({c['at'][:10]}):", "", c["body"].strip(), ""]
    if not issue["maintainer_comments"]:
        out += ["(none)", ""]
    out += ["## What the maintainer valued in earlier decisions", "", conventions(), "", "## Competing PRs", ""]
    for n in issue["prs"]:
        pr = _load(CACHE / "prs" / f"{n}.json")
        e = _load(CACHE / "edison" / f"pr-{n}.json") or {}
        a = _load(CACHE / "atlas" / f"pr-{n}.json") or {}
        p = pyth["prs"].get(str(n), {})
        out += [f"### PR #{n}: {pr['title']}", "",
                f"- Author: {(pr.get('author') or {}).get('login')}, opened {pr['createdAt'][:10]}, "
                f"+{pr['additions']} / -{pr['deletions']} in {pr['changedFiles']} files, diff: `prs/{n}.diff`",
                f"- Edison: **{e.get('verdict', 'not run')}** — {e.get('proven', 0)} tests fail before and pass after, "
                f"{e.get('unproven', 0)} pass either way, {e.get('broken', 0)} fail on the PR"
                + (f"; TypeScript tests not run: {len(e['ts_tests_not_run'])}" if e.get("ts_tests_not_run") else ""),
                ]
        if matrix:
            row = matrix["cells"].get(str(n), {})
            cells = ", ".join(f"#{m}'s tests {c['rate']:.0%}" if c["rate"] is not None else f"#{m}'s tests n/a"
                              for m, c in row.items())
            out.append(f"- Cross-test (this PR's code vs rivals' tests): {cells or 'n/a'}")
        if a.get("added") is not None:
            out.append(f"- Atlas: new errors in touched core files — ruff {a['added']['ruff']}, "
                       f"format {a['added']['format']}, mypy {a['added']['mypy']}")
        if p.get("copied_from"):
            out.append(f"- Pythagoras: most of its added code also appears in earlier PR #{p['copied_from']}")
        if pyth.get("summaries", {}).get(str(n)):
            out.append(f"- Approach: {pyth['summaries'][str(n)]}")
        body = (pr.get("body") or "").strip()
        out += ["", "PR description:", "", body[:3000] or "(empty)", ""]
    return "\n".join(out)


def stage(issue_number: int) -> None:
    """Write the case file and diffs into cache and into each satellite's working directory."""
    case_dir = CACHE / "tribunal" / str(issue_number)
    (case_dir / "case.md").parent.mkdir(parents=True, exist_ok=True)
    (case_dir / "case.md").write_text(case_file(issue_number), encoding="utf-8")
    issue = _load(CACHE / "issues" / f"{issue_number}.json")
    for name in SATELLITES:
        sat = satellite(name)
        dest = sat["workspace"] / "tribunal" / str(issue_number)
        (dest / "prs").mkdir(parents=True, exist_ok=True)
        shutil.copyfile(case_dir / "case.md", dest / "case.md")
        shutil.copyfile(HERE / "satellites" / f"{name}.md", dest / f"ROLE-{name}.md")
        for n in issue["prs"]:
            src = CACHE / "prs" / f"{n}.diff"
            if src.exists():
                shutil.copyfile(src, dest / "prs" / f"{n}.diff")
        give_to_owner(dest)


def give_to_owner(path: Path) -> None:
    """Files written into WSL from Windows land as root; hand them to the satellite's user so it can write its verdict."""
    m = re.match(r"^[/\\]{2}wsl(?:\.localhost|\$)[/\\]([^/\\]+)[/\\](.*)$", str(path))
    if not m:
        return
    distro, rest = m.groups()
    linux = "/" + rest.replace("\\", "/")
    user = linux.split("/")[2] if linux.startswith("/home/") else None
    if user:
        subprocess.run(["wsl.exe", "-d", distro, "-u", "root", "--", "chown", "-R", f"{user}:{user}", linux],
                       capture_output=True)


# Room ---------------------------------------------------------------------

MAX_DOC = 1_000_000  # Switch room documents hold at most 1 MiB
# Each document must fit in one tool result: a satellite that has to page through a bigger one
# reaches for shell commands, and those wait on an approval nobody may be there to give.
PART = 40_000
NOISE_RE = re.compile(r"(^|/)(uv\.lock|pnpm-lock\.yaml|package-lock\.json|yarn\.lock|poetry\.lock)$|\.snap$")


def split_diff(diff: str, size: int = PART) -> list[str]:
    """Cut a unified diff into parts of at most `size` characters at file boundaries (dropping lockfiles).
    A single file bigger than `size` is cut at line boundaries."""
    files = [f for f in re.split(r"(?m)^(?=diff --git )", diff) if f.strip()]
    files = [f for f in files if not NOISE_RE.search((re.match(r"diff --git a/\S+ b/(\S+)", f) or [None, ""])[1])]
    parts, current = [], ""
    for f in files:
        chunks = [f] if len(f) <= size else _cut_lines(f, size)
        for c in chunks:
            if current and len(current) + len(c) > size:
                parts.append(current)
                current = ""
            current += c
    if current:
        parts.append(current)
    return parts or [""]


def _cut_lines(text: str, size: int) -> list[str]:
    out, cur = [], ""
    for line in text.splitlines(keepends=True):
        if cur and len(cur) + len(line) > size:
            out.append(cur)
            cur = ""
        cur += line[:size]
    return out + ([cur] if cur else [])


def documents(issue_number: int) -> dict[str, tuple[str, str]]:
    """name -> (description, content) for everything a satellite needs, as room documents."""
    issue = _load(CACHE / "issues" / f"{issue_number}.json")
    docs = {"case": (f"Case file for #{issue_number}: issue, maintainer direction, evidence per PR",
                     (CACHE / "tribunal" / str(issue_number) / "case.md").read_text(encoding="utf-8"))}
    for name in SATELLITES:
        docs[f"role-{name}"] = (f"{name.title()}'s role brief and verdict format",
                                (HERE / "satellites" / f"{name}.md").read_text(encoding="utf-8"))
    for n in issue["prs"]:
        path = CACHE / "prs" / f"{n}.diff"
        text = path.read_text(encoding="utf-8") if path.exists() else ""
        if not text:
            docs[f"pr-{n}-1"] = (f"PR #{n} diff", "(GitHub would not serve this diff: too large)")
            continue
        parts = split_diff(text)
        for i, part in enumerate(parts, 1):
            docs[f"pr-{n}-{i}"] = (f"PR #{n} diff, part {i} of {len(parts)}", part)
    return docs


def attach_documents(agent: Agent, state: dict, issue_number: int) -> None:
    """Create the room's documents, or update the ones a previous kickoff made."""
    ids = state.setdefault("documents", {})
    for name, (description, content) in documents(issue_number).items():
        if name in ids:
            agent.op("update_room_document", document_id=ids[name], content=content)
        else:
            ids[name] = agent.op("create_room_document", name=name, description=description,
                                 instructions="Vegapunk tribunal material. Read-only evidence.",
                                 content=content)["document_id"]


def kickoff(issue_number: int) -> str:
    issue = _load(CACHE / "issues" / f"{issue_number}.json")
    shaka, lilith = satellite("shaka"), satellite("lilith")
    prs = ", ".join(f"#{n}" for n in issue["prs"])
    return (f"Tribunal open for issue #{issue_number}: {issue['title']}\n"
            f"{len(issue['prs'])} competing PRs: {prs}. Everything is attached to this room as documents: "
            f"`case` (issue, maintainer direction, Edison/Atlas/Pythagoras evidence), `role-shaka`, `role-lilith`, "
            f"and each PR's diff in parts `pr-<number>-1`, `pr-<number>-2`, ... "
            f"Load them with your Switch tool `load_internal_documents`, **one document per call** (each fits in "
            f"one read); the ids follow in the next message. Don't list directories, run shell commands, open files "
            f"or start subagents.\n\n"
            f"@{shaka['agent']} you are Shaka, the spec judge: follow `role-shaka` and post your verdict block here.\n\n"
            f"@{lilith['agent']} you are Lilith, the red team: follow `role-lilith` and post your verdict block here.\n\n"
            f"Stella decides: reply `pick #<pr> because <reason>` to record the final call.")


def open_tribunal(agent: Agent, issue_number: int, bridge: str, fresh: bool = False) -> dict:
    """fresh: archive the previous room and open a new one, so satellites start new sessions
    (a session stuck on an unanswered approval otherwise blocks every later mention in that room)."""
    stage(issue_number)
    state_path = CACHE / "tribunal" / str(issue_number) / "state.json"
    state = _load(state_path)
    attempt = (state or {}).get("attempt", 1)
    if state and fresh:
        agent.op("archive_room", room_id=state["room_id"])
        attempt += 1
        state = None
    if not state or state.get("bridge") != bridge:
        bridge_id, users = bridge_for(agent, bridge)
        issue = _load(CACHE / "issues" / f"{issue_number}.json")
        room = agent.op(
            "create_room", name=f"tribunal-{issue_number}" + (f"-{attempt}" if attempt > 1 else ""),
            description=f"Vegapunk tribunal for #{issue_number}: {issue['title']}"[:200],
            agent_names=["punk-records", satellite("shaka")["agent"], satellite("lilith")["agent"]],
            user_names=users, channel_type="channel_private", bridge_id=bridge_id,
            instructions=("Vegapunk tribunal. Satellites answer with one ```verdict``` JSON block as their role file "
                          "says. Read only: never run PR code, push, or comment on GitHub. "
                          "Only a human's `pick #N` decides."),
        )
        state = {"room_id": room["id"], "bridge": bridge, "attempt": attempt,
                 "opened_at": datetime.now(timezone.utc).isoformat()}
        _save(state_path, state)
    agent.attach(state["room_id"])
    attach_documents(agent, state, issue_number)
    _save(state_path, state)
    agent.say(state["room_id"], kickoff(issue_number))
    # hand over the ids so nobody explores directories or tool lists to find them (that needs approvals)
    ids = [f"{name} = {doc_id}" for name, doc_id in state["documents"].items()]
    chunk = ["Document ids for `load_internal_documents` (call it with one id at a time):"]
    for line in ids:
        if sum(len(l) + 1 for l in chunk) + len(line) > MAX_POST:
            agent.say(state["room_id"], "\n".join(chunk))
            chunk = []
        chunk.append(line)
    agent.say(state["room_id"], "\n".join(chunk))
    state["kicked_off_at"] = time.time()
    _save(state_path, state)
    print(f"tribunal #{issue_number} open in {bridge} room {state['room_id']}")
    return state


# Verdicts and decisions -----------------------------------------------------

def parse_verdict(text: str) -> dict | None:
    m = VERDICT_RE.search(text or "")
    if not m:
        return None
    try:
        v = json.loads(m.group(1))
    except json.JSONDecodeError:
        return None
    return v if isinstance(v, dict) and "scores" in v else None


def normalize(v: dict, prs: list[int]) -> dict:
    """Keep only this issue's PRs, as string keys; drop junk a model may add."""
    valid = {str(n) for n in prs}
    clean = lambda d: {str(k).lstrip("#"): x for k, x in (d or {}).items() if str(k).lstrip("#") in valid}
    return {"satellite": v.get("satellite"),
            "ranking": [int(str(p).lstrip("#")) for p in v.get("ranking", []) if str(p).lstrip("#") in valid],
            "scores": {k: float(x) for k, x in clean(v.get("scores")).items()
                       if isinstance(x, (int, float))},
            "notes": clean(v.get("notes")), "flags": clean(v.get("flags")),
            "confidence": v.get("confidence")}


def timeline(agent: Agent, room_id: str) -> list[dict]:
    ctx = agent.op("read_context", room_id=room_id, limit=200)
    entries = [e for t in ctx["threads"] for e in [t["root"], *t["replies"]] if e["kind"] == "message"]
    return sorted(entries, key=lambda e: e["timestamp"])


def collect(agent: Agent, issue_number: int) -> dict:
    """Latest verdict per satellite: the file it wrote if present, else its newest verdict block in the room."""
    issue = _load(CACHE / "issues" / f"{issue_number}.json")
    state = _load(CACHE / "tribunal" / str(issue_number) / "state.json")
    verdicts = _load(CACHE / "tribunal" / str(issue_number) / "verdicts.json") or {}
    names = {satellite(s)["agent"]: s for s in SATELLITES}
    for entry in timeline(agent, state["room_id"]):
        name = names.get(entry["sender_name"])
        if name and (v := parse_verdict(entry["body"])):
            verdicts[name] = normalize(v, issue["prs"])
        elif entry["sender_name"] not in names and entry["sender_name"] != "punk-records":
            record_pick(issue_number, entry)
    for name in SATELLITES:
        f = satellite(name)["workspace"] / "tribunal" / str(issue_number) / f"verdict-{name}.json"
        if f.exists():
            try:
                verdicts[name] = normalize(json.loads(f.read_text(encoding="utf-8")), issue["prs"])
            except (json.JSONDecodeError, ValueError):
                pass
    _save(CACHE / "tribunal" / str(issue_number) / "verdicts.json", verdicts)
    return verdicts


def record_pick(issue_number: int, entry: dict) -> bool:
    m = PICK_RE.search(entry["body"] or "")
    issue = _load(CACHE / "issues" / f"{issue_number}.json")
    if not m or int(m.group(1)) not in issue["prs"]:
        return False
    decisions = _load(CACHE / "decisions.json") or {}
    decisions[str(issue_number)] = {"pick": int(m.group(1)), "reason": m.group(2).strip()[:300],
                                    "by": entry["sender_name"], "at": entry["timestamp"]}
    _save(CACHE / "decisions.json", decisions)
    return True


def summary(issue_number: int) -> str:
    r = rank_issue(issue_number)
    lines = [f"Verdict for issue #{issue_number}: {r['title']}"]
    for i, row in enumerate(r["ranking"], 1):
        s = row["signals"]
        bits = [f"Edison {row['edison_verdict'] or 'n/a'}"]
        if s["cross"] is not None:
            bits.append(f"passes {s['cross']:.0%} of rivals' tests")
        if s["spec"] is not None:
            bits.append(f"Shaka {s['spec'] * 10:.0f}/10")
        if s["safety"] is not None:
            bits.append(f"Lilith {s['safety'] * 10:.0f}/10")
        if row["copied_from"]:
            bits.append(f"overlaps earlier #{row['copied_from']}")
        if row["high_flags"]:
            bits.append(f"flag: {row['high_flags'][0][:80]}")
        score = "n/a" if row["score"] is None else f"{row['score']:.2f}"
        lines.append(f"{i}. #{row['pr']} — {score} — " + "; ".join(bits))
    if r["pick"]:
        lines.append(f"Punk Records' pick: #{r['pick']} (confidence {r['confidence'] or 'n/a'}).")
    lines += [f"Disagreement: {d}" for d in r["disagreements"]]
    lines.append("Stella: reply `pick #<pr> because <reason>` to decide.")
    text = "\n".join(lines)
    return text if len(text) <= MAX_POST else text[:MAX_POST - 3] + "..."


def finish(agent: Agent, issue_number: int) -> None:
    """Post the ranking once per set of verdicts (the watch loop and `run` may both get here)."""
    state_path = CACHE / "tribunal" / str(issue_number) / "state.json"
    state = _load(state_path)
    verdicts = _load(CACHE / "tribunal" / str(issue_number) / "verdicts.json") or {}
    key = hashlib.sha256(json.dumps(verdicts, sort_keys=True).encode()).hexdigest()[:16]
    if state.get("finished_key") == key:
        return
    agent.say(state["room_id"], summary(issue_number))
    state.update({"finished_at": time.time(), "finished_key": key})
    _save(state_path, state)


def run(agent: Agent, issue_number: int, bridge: str, timeout: int, fresh: bool = False) -> dict:
    open_tribunal(agent, issue_number, bridge, fresh)
    deadline = time.time() + timeout
    verdicts = {}
    while time.time() < deadline:
        time.sleep(20)
        verdicts = collect(agent, issue_number)
        print(f"#{issue_number}: verdicts from {sorted(verdicts) or 'nobody yet'}", flush=True)
        if all(s in verdicts for s in SATELLITES):
            break
    finish(agent, issue_number)
    return verdicts


def watch(agent: Agent) -> None:
    """Live mode: react to verdicts and picks as events arrive on the stream."""
    def scan() -> dict[str, int]:
        return {_load(f)["room_id"]: int(f.parent.name) for f in (CACHE / "tribunal").glob("*/state.json")}

    rooms = scan()
    names = {satellite(s)["agent"] for s in SATELLITES}
    print(f"watching {len(rooms)} tribunal rooms", flush=True)
    for event in agent.events():
        if event.get("type") != "message":
            continue
        if event.get("room_id") not in rooms:
            rooms = scan()  # a tribunal opened (or reopened with --fresh) since we started
            if event.get("room_id") not in rooms:
                continue
        issue_number, payload = rooms[event["room_id"]], event["payload"]
        sender = payload.get("sender_name")
        if sender in names and parse_verdict(payload.get("body", "")):
            verdicts = collect(agent, issue_number)
            print(f"#{issue_number}: verdict from {sender}", flush=True)
            if all(s in verdicts for s in SATELLITES):
                finish(agent, issue_number)
        elif sender not in names and sender != "punk-records":
            entry = {"body": payload.get("body"), "sender_name": sender, "timestamp": payload.get("timestamp")}
            if record_pick(issue_number, entry):
                agent.say(event["room_id"], f"Recorded: Stella picked #{_load(CACHE / 'decisions.json')[str(issue_number)]['pick']}. "
                                            "I'll remember the reason in every later case file.")


def docket(agent: Agent, bridge: str) -> None:
    """One docket room per bridge with a line per issue."""
    state_path = CACHE / "tribunal" / f"docket-{bridge}.json"
    state = _load(state_path)
    if not state:
        bridge_id, users = bridge_for(agent, bridge)
        room = agent.op("create_room", name="vegapunk-docket", description="Vegapunk's ranked docket of competing PRs",
                        agent_names=["punk-records"], user_names=users, channel_type="channel_private",
                        bridge_id=bridge_id)
        state = {"room_id": room["id"]}
        _save(state_path, state)
    index = _load(CACHE / "index.json")["issues"]
    lines, chunk = [], []
    for n in sorted(index, key=int):
        if len(index[n]) < 2:
            continue
        r = rank_issue(int(n))
        if r["pick"] is None:
            continue
        lines.append(f"#{n} ({len(index[n])} PRs) → #{r['pick']} [{r['confidence'] or 'n/a'}] {r['title'][:50]}")
    for line in ["Vegapunk docket: issues with competing PRs and the current pick", *lines]:
        if sum(len(l) + 1 for l in chunk) + len(line) > MAX_POST:
            agent.say(state["room_id"], "\n".join(chunk))
            chunk = []
        chunk.append(line)
    if chunk:
        agent.say(state["room_id"], "\n".join(chunk))


def main() -> None:
    load_env()
    ap = argparse.ArgumentParser(description="Punk Records: tribunals for competing PRs")
    ap.add_argument("command", choices=["open", "collect", "run", "watch", "docket", "case"])
    ap.add_argument("issues", nargs="*", type=int)
    ap.add_argument("--bridge", default=os.environ.get("TRIBUNAL_BRIDGE", "discord"))
    ap.add_argument("--timeout", type=int, default=20 * 60, help="seconds to wait for verdicts in `run`")
    ap.add_argument("--fresh", action="store_true", help="archive the previous room and open a new one")
    args = ap.parse_args()
    agent = Agent.from_env()
    if args.command == "watch":
        return watch(agent)
    if args.command == "docket":
        return docket(agent, args.bridge)
    for n in args.issues:
        if args.command == "case":
            stage(n)
            print(CACHE / "tribunal" / str(n) / "case.md")
        elif args.command == "open":
            open_tribunal(agent, n, args.bridge, args.fresh)
        elif args.command == "collect":
            print(json.dumps(collect(agent, n), indent=1)[:2000])
            finish(agent, n)
        elif args.command == "run":
            run(agent, n, args.bridge, args.timeout, args.fresh)


if __name__ == "__main__":
    main()
