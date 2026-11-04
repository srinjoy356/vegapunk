# Vegapunk

**A council of AI agents, running inside [Switch](https://github.com/sandbox-quantum/switch), that ranks competing pull requests so a maintainer can pick one in minutes instead of days.**

Built for the [Flip the Switch hackathon](https://www.wemakedevs.org/hackathons/switch) (Track 01: Best Business Workflow).

## The problem

The Switch hackathon assigned every one of its 63 issues to everyone who asked, and the maintainers said "only one PR will be selected per issue." On day one there were already 149 competing PRs; most issues have two to six. Someone has to read every one, check it against the direction the maintainer wrote in the issue comments, run it, and choose. Reviewing, not writing, is now the bottleneck, and AI-written PRs make it worse.

## What Vegapunk does

Dr. Vegapunk split his mind into satellites that share one brain. Here each satellite is a different agent, on a different model, in one Switch room, and a human makes the call.

| Satellite | Role | Runs as |
|---|---|---|
| **Edison** | Builds every PR in a no-internet Docker sandbox and runs its own tests twice: on the PR and on its base. A test that fails before and passes after **proves** the change. Covers switch-core's Python tests and the Console packages' vitest tests. Then runs every rival's tests against every PR (the cross matrix). | Deterministic (Docker on WSL) |
| **Atlas** | Lint, format and type errors the PR adds to the files it touches (head minus base, so old errors aren't blamed on it). | Deterministic (ruff, mypy) |
| **Pythagoras** | Compares the rivals: size, scope, and how much of a PR's code already appears in an earlier rival. One-line summary of each approach. | Deterministic + gpt-4o-mini |
| **Shaka** | The spec judge: does each PR do what the issue and the maintainer's later comments asked? | Claude Code agent in Switch (Windows) |
| **Lilith** | The red team: secrets, unsafe defaults, injection, cheating tests. | Antigravity / Gemini agent in Switch (Linux) |
| **York** | Logs every paid model call and enforces a hard $1 cap for the whole run. | Ledger |
| **Punk Records** | The shared brain: a custom agent written directly against Switch's agent protocol. Opens a tribunal room per issue, briefs the satellites, collects their verdicts, ranks, keeps the docket, and remembers why the human picked what they picked. | Python, SSE + HTTP |
| **Stella** | The human maintainer. Replies `pick #1215 because …` in the room; that is the only thing that decides. | You |

```
GitHub issue + maintainer comments + competing PRs   (vegapunk.ingest)
        |
        v
Edison + Atlas sandbox in WSL Docker                  (vegapunk.edison)
Pythagoras comparison                                 (vegapunk.pythagoras)
        |
        v
Punk Records opens "tribunal-<issue>" in Discord / Slack / Mattermost via Switch
   attaches the case file, role briefs and every diff as room documents, kickoff mentions Shaka and Lilith
        |
        v
Shaka (Claude) and Lilith (Gemini) post ```verdict``` JSON blocks in the room
        |
        v
Punk Records ranks (vegapunk.rank), posts the result, Stella picks, Punk Records remembers
```

### Why Switch is central

Without Switch this is a pile of scripts with no shared room and no human in the loop. Vegapunk uses Switch for:
- **Rooms in the apps teams already use**: every tribunal is a private channel in Discord, Slack or Mattermost with the satellites and the human in it.
- **Any agent, any model**: Shaka is Claude Code on Windows, Lilith is Antigravity (Gemini) on Linux, Punk Records is our own protocol client. One room, three vendors (with gpt-4o-mini for Pythagoras).
- **The agent protocol**: Punk Records registers as an `always_on` agent, holds an SSE event stream with a 2-second heartbeat, and calls operations (`create_room`, `read_context`, `list_bridges`, …).
- **Addressing policies**: each satellite only takes work from its owner's agents and Punk Records (custom rules), so nobody else in a room can redirect them.
- **Shared context**: the evidence is attached to the room as Switch room documents (read with Switch's own document tool, so satellites need no file access and no approvals), and the kickoff, verdicts and Stella's pick live in the room's history, so anyone joining sees the whole trail.

## Measured, not claimed

1. **Planted defects** (`vegapunk.planted`): take PRs Edison proved, plant known faults (implementation removed, tests hollowed, tests skipped, a fake secret added) and check each one is caught.
2. **Backtest** (`vegapunk.backtest`): this repository has no decided competing-PR issues before the hackathon (every issue with two or more PRs is a hackathon issue still open), so the backtest asks the question the history can answer: across 40 past PRs, half merged and half closed unmerged, does Edison's evidence predict which got merged?
3. **Sealed prediction** (`vegapunk.seal`): after PRs close on Nov 7, Vegapunk ranks every contested issue and publishes only the SHA-256 of the rankings (`predictions/*.sha256`). When the maintainers choose, `seal reveal` checks the hash and scores top-1/top-3 agreement with their real picks. Nobody can adjust the rankings after the fact.

Results so far are in [docs/results.md](docs/results.md) and the rendered docket (`python -m vegapunk.report`). The day-by-day commands, including sealing and revealing, are in [docs/runbook.md](docs/runbook.md).

## Run it

Requirements: Python 3.12+, [uv](https://docs.astral.sh/uv/), Docker on a Linux host (WSL2 works), Switch Console with a server, a GitHub token, and optionally an OpenAI key.

```bash
uv sync
cp .env.example .env        # fill in GITHUB_TOKEN, SWITCH_API_URL, SWITCH_REGISTRATION_TOKEN, ...
uv run python -m vegapunk.ingest                       # cache issues, maintainer comments, PRs, diffs
```

On the Linux host with Docker (WSL: `cd /mnt/c/<repo>`, `export UV_PROJECT_ENVIRONMENT=~/vegapunk-work/venv`):

```bash
git clone https://github.com/sandbox-quantum/switch ~/vegapunk-work/switch
uv run python -m vegapunk.edison --issue 803 --matrix --atlas
```

Then, with Switch Console open:

```bash
uv run python -m vegapunk.pythagoras 803
uv run python -m vegapunk.tribunal run 803 --bridge discord   # opens the room, waits for verdicts, posts the ranking
uv run python -m vegapunk.tribunal watch                      # live: verdicts and Stella's picks from the event stream
uv run python -m vegapunk.report                              # cache/report/index.html
```

Registering Punk Records once: see `vegapunk/switch.py` (`register`). Satellites are ordinary Switch Console agents; add `punk-records` to their "Who can talk to your agent" rule. Setup notes for Windows + WSL, including every wall we hit, are in [docs/blog-notes.md](docs/blog-notes.md).

## Safety and fairness

- **Read-only on GitHub.** Vegapunk never comments on, labels or reviews anyone's PR.
- **Untrusted code only runs sandboxed**: no internet, all capabilities dropped, read-only root filesystem, memory/CPU/PID limits, and a throwaway Postgres on a private network. The tests' Postgres fixture is redirected by a pytest plugin so the sandbox never touches the Docker socket.
- **Conflict of interest.** We also send Track 03 PRs. Our own PRs are excluded from the sealed rankings, and the rankings stay sealed until the maintainers have decided.
- **Satellites are read-only**: their role files forbid running PR code, pushing, commenting, or printing environment variables, and Console's per-action approvals stay on.
- **Paid calls are capped** by York at $1 total.

## Limits

- Edison runs switch-core's Python tests and the Console packages' vitest tests (`--ts`). The desktop app's Electron/browser tests, Gateway tests and `*.integration` tests are listed but not run.
- Unattended satellites stall on any tool that needs a human approval (shell, file writes); the tribunal avoids them by design, and `--fresh` reopens a stuck tribunal in a new room.
- A PR that changes dependencies runs against an image built from its own lockfile.
- Satellite scores are model opinions; the ranking always shows them next to Edison's facts, and disagreements are printed, not averaged away.
