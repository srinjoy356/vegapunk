# I built a council of AI agents to judge 149 competing pull requests. Here's what broke.

*Draft for the Flip the Switch "Best Blog" side track. Numbers are from day 1; update before publishing.*

The Switch hackathon has a Track 03 for core contributions. Every one of its 63 issues was assigned to everyone who asked, and the maintainers said one PR would be picked per issue. On day one there were already 149 competing PRs, two to six per issue. Somebody has to read all of them, check each against what the maintainer said in the comments, run them, and choose.

So I built **Vegapunk**: a council of AI agents that does that work inside [Switch](https://github.com/sandbox-quantum/switch), with a human making the final call. The name comes from One Piece: Dr. Vegapunk split his mind into satellites that share one brain.

## The council

- **Edison** runs every PR's own tests in a no-internet Docker sandbox, twice: on the PR, and on the commit it branched from. A test that fails before and passes after *proves* the change. Then it runs every rival's tests against every PR.
- **Atlas** counts the lint, format and type errors a PR adds (head minus base, so old errors aren't blamed on it).
- **Pythagoras** compares the rivals and writes a one-line summary of each approach (gpt-4o-mini).
- **Shaka** (Claude Code, on Windows) judges each PR against the issue and the maintainer's later comments.
- **Lilith** (Antigravity / Gemini, on Linux) red-teams each PR: secrets, unsafe defaults, cheating tests.
- **York** logs every paid model call and stops at $1 for the whole hackathon.
- **Punk Records** is the shared brain: a custom agent I wrote directly against Switch's agent protocol. It opens a private tribunal channel per issue in Discord (or Slack, or Mattermost), attaches the evidence, briefs the satellites, collects their verdicts and ranks the PRs.
- **Stella** is the human. Typing `pick #1387 because …` in the channel is the only thing that decides.

Switch is what makes this one workflow instead of a pile of scripts: the channel is the room, three vendors' agents sit in it together, the evidence lives in the room as shared documents, and anyone who joins sees the whole trail.

## What it said about a real issue

Issue #803 asks to show what an agent's tool actually ran, safely. Three PRs; Edison proved all three (84, 243 and 119 tests that fail before and pass after). Then the satellites disagreed, usefully:

- Shaka: #1387 9/10. #1215 3/10, because it "adds a per-agent column and `!tool-details @agent` command … both directly contradict" the maintainer's direction.
- Lilith: #1414 safest. #1215 gets a *critical*: it puts raw tool output into the session item text, so unredacted output is journaled and published.

Punk Records' pick: #1387 at medium confidence, with the disagreement printed rather than averaged away. On #771 (scheduled messages) everyone agreed: #1153, high confidence; Lilith found that its rival's background runner escalates orphaned schedules to admin authority.

## Measuring it instead of claiming it

**Planted defects.** I took PRs Edison had proven and planted known faults in copies:

- Implementation removed, tests kept.
- Every test body replaced with `pass`.
- Every test skipped.
- A fake AWS key and GitHub token added.

The first run was embarrassing in the best way. The hollow tests still came back "Proven", 38 of them. They still import the PR's new module, so on the base commit they can't even be collected, and Edison was counting "couldn't load before" as "failed before". Edison now reads each test's syntax tree and won't count a test that asserts nothing as proof. After that fix it caught 12 of 12.

The fake secret is invisible to tests by design, so I ran a blind tribunal: the original PR against its secret-planted twin, same title, made-up number. Lilith flagged both lines as **critical** with exact line numbers and scored the twin 0/10. Shaka, the *spec* judge, flagged it too.

**Backtest.** This repository has no past issues where competing PRs were decided (every multi-PR issue is a hackathon issue still open), so I asked what history can answer: across 40 past PRs, half merged and half closed, does Edison's evidence predict a merge? Proven PRs were merged 58% of the time, broken ones 17%, unproven ones 0%. AUC 0.79.

**Sealed prediction.** On Nov 7 Vegapunk ranks every contested issue and I publish only the SHA-256 of the rankings. When the maintainers choose, the file is revealed and scored. No adjusting after the fact.

## The walls (the part I'd want to read)

1. **"Antigravity: not installed", while Antigravity was installed.** Switch Console needs `antigravity-acp`, a separate Google server with its own sign-in, and it only ships for macOS and Linux. Lilith lives in WSL Ubuntu.
2. **Console only lets a local server use local agents.** So the Switch server moved into Ubuntu too, and Console bridges it back to Windows over SSH so Claude on Windows can still join.
3. **Mirrored WSL networking broke that bridge** ("port already in use"), because it also publishes Ubuntu's container ports on Windows. The fix: turn off WSL port forwarding and reach sshd through `wsl.exe` itself: `ProxyCommand wsl.exe -d Ubuntu -u srinjoy -- nc 127.0.0.1 2222`.
4. **My custom agent belonged to "Agent Bootstrap", not me.** Satellites that only take work from their owner's agents refused it. Addressing policies are real access control; I gave each satellite a custom rule naming `punk-records`.
5. **Unattended agents stall on approvals.** The first tribunals never finished. Shaka's file write failed inside Console's permission bridge and it fell back to PowerShell, which waits for someone to click Allow in Discord. Lilith ran `ls` to discover her own tools: same thing. And a session stuck on an approval blocks every later mention in that room. The fix made the design better: the evidence became Switch **room documents** read with Switch's own tool (no approval), split into parts that each fit one read, with the document ids posted in the room so nobody goes looking.
6. **Testcontainers vs. a sandbox.** switch-core's tests start Postgres through the Docker socket, and giving untrusted PR code that socket would defeat the sandbox. A 30-line pytest plugin swaps the container class for one pointing at a throwaway Postgres on a private, internet-less Docker network.
7. **8 GB is a design constraint.** Seven idle Antigravity sessions plus a pnpm install of the Console workspace got OOM-killed at a load average of 462.

## What I'd tell the next person

- Make the room the workspace. If your agents need files, shells or approvals to do the job, an unattended workflow will stall.
- Let the measurement attack the system. The planted-defect harness found a hole in Edison that no amount of reading the code had.
- Print disagreements. Two models from two vendors disagreeing about #803 was the most useful output of the day.

Code: [repo link]. Results: `docs/results.md`.
