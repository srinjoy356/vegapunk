# Submission pack

Everything here is ready to paste or read. Numbers marked **(refresh)** change as Edison finishes: take the final ones from `docs/results.md` right before you submit.

## 1. Form text

**Project name:** Vegapunk

**One-line pitch:** A council of AI agents inside Switch that ranks the competing pull requests for each hackathon issue, so a maintainer can pick one in minutes instead of days.

**Track:** Track 01, Best Business Workflow. Also enter: Best Blog, and Code with Wispr if you have the scorecard.

**Short description (about 120 words):**
The Switch hackathon gave every issue to everyone who asked, and "only one PR will be selected per issue", so maintainers must read, run and compare 149+ PRs (2 to 6 per issue). Vegapunk does that inside Switch. Edison proves each PR in a no-internet Docker sandbox by running its tests on the PR and on its base (a test that fails before and passes after proves the change) and runs every rival's tests against every PR. Atlas counts new lint and type errors. Shaka (Claude Code) judges the spec and the maintainer's later comments; Lilith (Antigravity/Gemini) red-teams. Punk Records, a custom Switch agent, opens a private channel per issue in Discord, collects verdicts and ranks the PRs. A human decides with `pick #N because ...`.

**How Switch is used:** Rooms in Discord/Slack/Mattermost, one per issue. Shaka (Claude Code), Lilith (Antigravity) and Punk Records (custom agent on the raw agent protocol: SSE stream, 2 s heartbeat, `create_room`, `read_context`, room documents) work in the same room. Evidence is attached as Switch room documents. Addressing policies restrict who can instruct each satellite. Without Switch there is no shared room, no human gate and no multi-vendor council.

**Repo:** https://github.com/srinjoy356/vegapunk

**Links to fill in:** demo video URL, blog URL, social post URL.

## 2. Numbers to quote **(refresh)**

- 65 hackathon issues, 149 competing PRs on day 1; 47 issues have 2 or more PRs.
- Backtest: 40 past PRs, AUC 0.79; PRs Edison proves are merged 58% of the time, broken ones 17%, unproven ones 0%.
- Planted defects: implementation removed, tests hollowed, tests skipped = 12/12 caught by Edison. A planted fake AWS key and GitHub token were flagged critical/high by Lilith and high by Shaka in a blind tribunal.
- Paid model spend: under $0.01 of the $1 cap (`python -m vegapunk.york`).
- Tribunals with both satellites: see `docs/results.md`.

## 3. Demo video script (about 3 minutes)

Record the screen with sound. Keep Discord on one side and the terminal or `cache/report/index.html` on the other.

| Time | Show | Say |
|---|---|---|
| 0:00 | The hackathon issues page, then `ls cache/prs \| wc -l` | "The Switch hackathon has over 60 issues, each assigned to everyone who asked, and one PR gets picked per issue. That is already 149 competing PRs. Reviewing is the bottleneck." |
| 0:20 | README diagram | "Vegapunk is a council of agents inside Switch. Edison runs tests, Atlas lints, Shaka reads the spec, Lilith attacks, Punk Records runs the room, and a human decides." |
| 0:40 | Edison on one PR: `cache/edison/pr-1387.json` | "Edison runs each PR's own tests twice, on the PR and on the commit it started from. 243 tests fail before and pass after, so this PR really changes behaviour." |
| 1:00 | Discord `#tribunal-803`: kickoff, documents, verdicts | "Punk Records opened this private channel through Switch, attached the evidence as room documents, and asked Claude and Gemini. They are different vendors in one room." |
| 1:30 | The posted ranking, the disagreement line | "Shaka prefers 1387 because the others contradict the maintainer's direction. Lilith found a critical leak in 1215. They disagree about first place and Vegapunk prints that instead of hiding it." |
| 1:50 | Reply `pick #1387 because it follows the opt-in direction` and the watch log | "I decide. Punk Records records the reason and uses it in every later case." |
| 2:05 | `docs/results.md`: planted defects and the secret test | "I tested it: I planted faults in proven PRs. The first run exposed a hole, hollow tests still counted as proof. I fixed it and Edison caught 12 of 12. A planted fake key was flagged critical by Lilith." |
| 2:30 | Backtest table, sealed hash file | "On 40 past PRs, Edison's evidence predicts a merge with 0.79 AUC. On Nov 7 I seal the rankings with a SHA-256 and score them against what the maintainers actually choose." |
| 2:50 | Repo and README | "Everything is open source and reproducible. Thanks." |

**Wispr:** if entering Code with Wispr, dictate this script and the README edits with Wispr Flow, then screenshot Insights for the submission.

## 4. Social post (#HowISwitch)

> Built Vegapunk for #HowISwitch: a council of AI agents in Switch that ranks the 149 competing PRs in the hackathon. Claude and Gemini agents + a sandbox that proves each PR's tests fail before and pass after, in one Discord room, with a human making the call. I'm sealing my predictions with a SHA-256 and will score them against what the maintainers choose. Repo + demo: <links> @switch

After sealing, add: `Sealed ranking hash: <sha256>`.

## 5. Publishing checklist

- [x] Public repo created and pushed: https://github.com/srinjoy356/vegapunk
- [ ] Edison finished; `uv run python -m vegapunk.council --top 8` done; `uv run python -m vegapunk.report` and `python -m vegapunk.results` regenerated.
- [ ] Record the demo (section 3), upload (YouTube unlisted works), paste link above.
- [ ] Publish `docs/blog-draft.md` (dev.to, Hashnode or Medium), refresh its numbers, link the repo.
- [ ] Seal late on Nov 7: `uv run python -m vegapunk.seal seal`, commit and push `predictions/*.sha256`, post the hash.
- [ ] Submit on the WeMakeDevs page before 11:59 PM IST on Nov 7: repo, video, blog, README (shows how Switch is used).
- [ ] Optional Track 03: a PR to sandbox-quantum/switch for an assigned `hackathon` issue (tag the maintainer in the issue first).

## 6. Pushing the repo

Create an empty public repo named `vegapunk` on GitHub (no README), then:

```bash
git remote add origin https://github.com/srinjoy356/vegapunk.git
git push -u origin main
```

`.env` and `cache/` are gitignored; `predictions/` is meant to be committed (only the hash file; the rankings stay in `cache/predictions/` until reveal).
