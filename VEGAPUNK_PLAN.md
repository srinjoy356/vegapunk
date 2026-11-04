# Vegapunk: plan for Flip the Switch (Nov 4-7, 2026)

## Status (Nov 4, evening): what changed from the plan below

- Built: ingester, Edison (sandbox, proof, cross matrix), Atlas, Pythagoras, York, Punk Records (protocol agent, tribunals, docket, picks), ranker, sealed prediction, report, results, planted-defect harness, backtest. See README.md.
- Real numbers: 149 competing PRs on day 1 (not 400-600); expect more by Nov 7.
- Satellites: Shaka = Claude Code on Windows, Lilith = Antigravity (Gemini) on WSL Ubuntu; Pythagoras = gpt-4o-mini; Atlas is deterministic (ruff, mypy), not an LLM.
- Backtest changed: the repo has no decided competing-PR issues before the hackathon, so it measures merge prediction on 40 past PRs; the competing-PR question is answered by the sealed prediction.
- Track 03: #803 already has 3 Proven PRs and #771 has 2. Best opening found: #822 (Microsoft 365 connector) with no PR yet. Also a Console bug worth reporting: remote-host readiness uses Windows `where` on Linux hosts; and Claude Code's Write permission request fails with a ZodError ("updatedInput expected record") inside Console sessions.

## 1. What we are actually being judged on

Hackathon: WeMakeDevs x DevTools Academy, sponsor Switch (sandbox-quantum/switch, ~3.5k stars).
Deadline: **Nov 7, 11:59 PM IST**. Team up to 4.

Judging criteria (weights not shown on the page):
1. **Use of Switch**: the project must stop working without Switch.
2. **Technical execution**: someone can clone it and reproduce it.
3. **Creativity and impact**: a fresh idea that solves a problem a real team has.
4. **Presentation**: demo video and README make the Switch usage obvious.

Prizes we can stack in one hackathon:
| Track | Prize | Our entry |
|---|---|---|
| 01 Best Business Workflow | $2,000 | **Vegapunk (main project)** |
| 03 Best Core Contribution | $100 per PR, top 20 (judging text says top 10) | 3-4 deep PRs Vegapunk itself needs |
| Code with Wispr (side) | $500 | Last phase, as you asked (risk noted in section 8) |
| Best Blog (side) | AirPods | Write-up of the backtest results |
| #HowISwitch posts | keyboards, top 5 | Post the live results |

## 2. The real problem sitting in plain sight

The Switch maintainers have a problem right now, and the numbers are public:

- **305 open PRs** on sandbox-quantum/switch, 948 closed, 674 merged.
- All **63 hackathon issues** are assigned to everyone who asked: 4 to 10 people each.
- The maintainer's own words on the issues: PRs "will be reviewed after the hackathon time window. Only one PR will be selected per issue."
- So after Nov 7 one or two maintainers must read roughly 400-600 competing PRs, check each against the direction they wrote in issue comments (e.g. "make it opt-in", "don't add server-side Zendesk tools", "use the pattern-validated ApiKeyField"), run them, and pick one per issue.

This is not a Switch-only problem. Every popular open-source project (and every company with many contributors or many coding agents) is drowning in PRs, and AI-generated PRs are making it worse. Reviewing is now the bottleneck, not writing.

**Vegapunk is a Switch-native review council: a room of specialist AI agents on different harnesses that reviews competing PRs against the maintainer's stated intent, runs them in a sandbox, and puts a ranked, evidence-backed verdict in front of a human who makes the call in Slack/Discord/Mattermost.**

Why this wins on each criterion:
- **Use of Switch**: it is a multi-agent, multi-harness, human-gated workflow. That is exactly Switch's pitch ("any agent, shared context, people in the loop"), and it uses rooms, room templates with kickoff, linked rooms, roles, task delegation, budgets and the agent protocol. Without Switch you have a pile of scripts with no shared room and no human gate.
- **Impact**: it solves the judges' own pain this week. We can hand it to them.
- **Measurable in real life**: section 5. We do not claim impact, we pre-register predictions and get scored by reality.
- **Hard**: sandboxed execution of untrusted code across a Python + TypeScript monorepo, cross-model adversarial review, a custom agent written against the raw SSE/HTTP agent protocol, a backtest harness over ~950 historical PRs.

## 3. The One Piece mapping (it is not just branding, it is the architecture)

Vegapunk split his mind into satellites that share one brain, Punk Records. Switch rooms with shared context are literally that.

| Satellite | Trait | Role in the council | Harness (diversity on purpose) |
|---|---|---|---|
| **Shaka** | Good / logic | Spec judge: checks the PR against the issue's "Done when" list and every maintainer direction comment. Owns the final score sheet. | Claude Code |
| **Lilith** | Evil | Red team: secrets, injection, auth bypass, unsafe defaults, license problems. Many Switch issues are marked security-sensitive. | Antigravity (Gemini) |
| **Edison** | Thinking | Reproducer (absorbs Punk Hazard): builds the PR in a throwaway Docker container, runs the repo's own tests and lint, and proves the PR with a **fail-before / pass-after** test (section 3a). | Claude Code |
| **Pythagoras** | Wisdom / data | Comparator: diffs competing PRs for the same issue, finds copy-paste between them, AI slop, scope creep, and duplicated work. | Antigravity (Gemini) |
| **Atlas** | Force | Stress: runs the heavier checks (type check, full test matrix, migrations up/down) only on the shortlist. | Antigravity (Gemini) |
| **York** | Greed | Quota keeper: no paid API at all. Tracks how much of the Claude Pro and Antigravity allowance each review uses, queues work when a limit is near, reports usage per PR. | Antigravity (Gemini) |
| **Punk Records** | Shared brain | Custom Python agent written directly on the agent protocol (SSE in, HTTP out). Holds the maintainer's conventions (CONTRIBUTING, CLAUDE.md, design docs, past review comments) and **learns from every human decision**. | Our own code |
| **Stella** | The original | The human maintainer. Only Stella's confirmation closes a verdict. | Human |

### 3a. Punk Hazard inside Edison: fail-before, pass-after

A PR that claims to work is weak evidence. A PR with a test that fails on the base commit and passes on the PR's head is strong evidence. For every PR, Edison:

1. Takes the PR's own new or changed tests and runs them on the **base** commit, then on the **head** commit.
2. If the PR has no such test, writes one from the issue's "Done when" list and the bug report, then runs it the same way.
3. Records one of four outcomes:

| Outcome | Meaning | Effect on score |
|---|---|---|
| **Proven** | Test fails on base, passes on head | Strong boost |
| **Unproven** | Test passes on both (it doesn't test the change) | Penalty; Lilith asks why |
| **Broken** | Test fails on head | Heavy penalty |
| **Unreproducible** | Can't build or Edison can't write a meaningful test | Flagged for Stella, no auto-score |

4. Runs every competing PR for the same issue against **every other PR's proving tests**. A PR that passes its rivals' tests too is the most complete one. This cross-test matrix is the single strongest ranking signal, and it's objective.

Lilith checks each Edison test for cheating (asserting nothing, mocking out the code under test, skipping on CI). The same before/after test also scores the backtest: for historical bug issues with a known fix commit, "Edison reproduced it" is a yes or no fact.

Why different harnesses: agents built on the same model make the same mistakes. Disagreement between Claude, GPT and an open model is a signal, and Vegapunk surfaces it instead of averaging it away.

## 4. How it runs inside Switch

```
GitHub issue #N (+ its maintainer comments) + all PRs that say "Closes #N"
        |
        v
Punk Records agent (agent protocol) creates room "Tribunal #N" from a room template
        |   kickoff mentions the satellites; room instructions = issue + direction comments
        v
+---------------- Tribunal #N (Slack / Discord / Mattermost room) ----------------+
|  Edison builds + tests each PR in Docker   Lilith audits diffs                  |
|  Pythagoras compares PRs                   Atlas stress-tests the shortlist     |
|  York posts running cost                   Shaka writes the score sheet         |
|  Stella (human) asks questions, overrides, confirms                             |
+----------------------------------------------------------------------------------+
        |  verdict + evidence
        v
"Docket" linked room: one line per issue, ranked PRs, confidence, cost, open disagreements
        |
        v
Punk Records records Stella's decision -> updates conventions -> next tribunal is better
```

Switch features this exercises: room templates with params and kickoff, linked rooms, agent roles, `task_delegate` / `task_update` / `task_finalise` events, addressing policies, budgets, multiple harnesses in one room, Mattermost locally (no Slack admin needed for the demo).

Safety rules built in from day one:
- **Read-only on GitHub by default.** Vegapunk never comments on other people's PRs unless the maintainer turns it on. No spam.
- Untrusted PR code only runs in a container with no network and no secrets.
- **Conflict of interest**: we also send Track 03 PRs. Vegapunk's rankings of hackathon PRs stay sealed (section 5) and our own PRs are excluded from our rankings. Say this openly in the README.

## 5. How we measure it in real life

Three measurements, from cheapest to most convincing.

**A. Backtest on history (ready by day 3).** The repo has ~950 closed PRs, 674 merged and ~270 closed without merge. That is a labelled dataset. Run Vegapunk on a sample (e.g. 100 PRs, balanced) with the repo state at the time and report:
- merge prediction accuracy, precision and recall for "will be merged",
- for issues with more than one PR, top-1 agreement with the PR that was actually merged,
- for closed bug issues with a known fix commit, Edison's reproduction rate (test fails before the fix, passes after),
- against baselines: "newest PR wins", "largest diff wins", and a single-agent LLM judge (to prove the council beats one model).

**B. Planted defects (ready by day 3).** Take 20 merged PRs and inject known faults: a leaked token, a removed test, a broken migration, an unchecked input, an off-spec behaviour that contradicts a maintainer comment. Report detection recall per satellite. This proves Lilith and Edison actually do something.

**C. Sealed live prediction (the headline).** On Nov 7, after PRs close, Vegapunk ranks every PR for each of the 63 hackathon issues. We publish **only the SHA-256 hash** of the rankings file (in a public commit and a social post). When the maintainers announce the selected PR per issue, we reveal the file and score our top-1 and top-3 agreement against their real choices. This is a pre-registered prediction: we cannot fudge it, and anyone can check it. Results may land after judging; the pre-registration itself is the demo, and the reveal is a great #HowISwitch post and blog follow-up.

Also report per PR: wall-clock minutes, dollars (York), and how often satellites disagreed. Compare with a stated human estimate (e.g. 20 minutes per PR) to give hours saved for the 400-600 PR backlog.

Be honest in the README about what A, B and C do and do not show.

## 6. Track 03: core PRs that Vegapunk needs

Facts from the issues:
- Only `hackathon`-labelled issues count. Everyone who asked is now assigned; **one PR is chosen per issue**, reviewed after Nov 7.
- Security-sensitive issues require posting a design in a comment first. That filters out low-effort entries, which is good for us.
- Low-effort and unreviewed AI PRs are not judged.

Pick on three tests: we need it for Vegapunk, competition is lower, and it is deep enough that quality decides.

| Issue | Why it fits | Assignees |
|---|---|---|
| #803 Show tool input and output in the channel, safely | Stella must see what Edison actually ran. Security-sensitive, maintainer already gave detailed direction (opt-in, redaction, 2,000/500 char caps, mask host secrets with its own test). Hard, high-value. | 8 |
| #802 Show running subagents on the activity card | Satellites spawn subagents; the room should show it. | 7 |
| #771 Scheduled messages to agents in a room | Nightly docket run ("@shaka review new PRs at 02:00"). | 7 |
| #801 Deliver messages sent mid-turn to the running agent (steering) | Stella redirects a satellite mid-review. Deep in the session host. | 7 |

Lower-competition fallbacks (4 assignees each) if we have capacity: #792 Signal, #796 SMS (Twilio), #776 Kimi Code provider, #778 GitHub Copilot CLI provider, #785 Auggie provider.

Rules for ourselves: read every maintainer comment on the issue before coding, post the design first when the issue says so, sign the CLA, link with `Closes #N`, include tests and the short video the issue asks for, and cap at 3-4 PRs we can do well rather than 10 thin ones. Vegapunk can review our own PRs before we open them (a nice demo moment), but we do not rank ourselves in section 5C.

## 7. Schedule (IST)

Split assumes 2-4 people; with fewer, cut from the bottom of each day.

**Nov 4 (today): foundations**
- Install Switch Console (Windows build exists) and Docker; run the 10-minute quickstart with Mattermost.
- Get one Claude Code agent and one Codex agent into one room. Read `docs/official/internals/agent-protocol.md` and `docs/TEMPLATES.md`.
- GitHub ingester: issue + maintainer comments + linked PRs + diffs into a local cache (use a token; the unauthenticated API limit is 60 requests an hour).
- Comment on the chosen Track 03 issues; start the #803 design comment.

**Nov 5: the council works end to end on one issue**
- Room template `tribunal.template.yaml` with kickoff; satellite instructions.
- Edison's sandbox: Docker image with uv + pnpm, per-PR worktree, no network, run `just check` and `just test` subsets.
- Punk Records agent on the raw protocol: registration, SSE stream, heartbeat every 2s, room creation, docket room.
- First full tribunal on a real closed issue. Start Track 03 coding.

**Nov 6: measurement**
- Backtest harness (A) and planted-defect suite (B); run overnight.
- York's cost tracking via budgets. Shaka's score sheet format.
- Open the Track 03 PRs.

**Nov 7: results and submission**
- Freeze, run 5C on the hackathon issues as soon as possible, commit the hash.
- Demo video (3 minutes: the problem in numbers, one live tribunal in Mattermost/Discord, Stella overriding a verdict, backtest table, sealed hash).
- README with reproduce steps, results, limits and the conflict-of-interest note.
- Blog post draft, #HowISwitch post.
- **Wispr phase last**, per your call (section 8).

## 8. Risks and decisions

- **Scope is large for 3.5 days.** The minimum that still wins: one tribunal running end to end on Mattermost with three satellites (Shaka, Lilith, Edison) + Punk Records + backtest A. Everything else is extra.
- **No paid API: Claude Pro + Antigravity only.** Usage limits, not money, are the constraint. So the pipeline is deterministic first: building, running tests, the fail-before/pass-after check and the cross-test matrix cost zero tokens and run on every PR. Antigravity (Gemini) does the bulk reading (Lilith, Pythagoras, Atlas). Claude Pro is saved for Shaka's verdict on the top 3 PRs per issue and for writing Vegapunk itself. Backtest sample shrinks to about 40 PRs. York queues work when a limit is close. **gpt-4o-mini (OpenAI key in .env) runs Punk Records and Pythagoras** as the third vendor; York logs tokens and dollars per PR and per tribunal and has a **hard cap of $1** for the whole hackathon: when reached it pauses and asks before spending more. Expected total spend is under $2 even at full scale, so the cap mainly stops runaway agent loops.
- **Wispr at the very end**: the Wispr prize asks for an Insights usage scorecard, which counts how much you dictated. Doing it only at the end means a small scorecard. If you want that $500, dictating prompts from day 1 costs nothing extra; otherwise treat it as a bonus and dictate the README, room instructions and blog at the end.
- **Windows**: Switch Console on Windows is early access. If it fights us, run the agents in WSL or on a Linux VM.
- **Judges may see ranking competitors' PRs as awkward.** Sealed hashes, exclusion of our own PRs, and read-only GitHub access handle this; offering Vegapunk to the maintainers as a tool turns it into a gift.

## 9. Alternatives considered (and why not)

- **Incident response council**: Switch's own demo is already an incident room, so it looks derivative.
- **Personal/creative track idea**: same prize money, but far weaker on "solves a problem a real team has" and harder to measure.
- **Only Track 03 PRs**: max $100 each and every issue has 4-10 competitors.
