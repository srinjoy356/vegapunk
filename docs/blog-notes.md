# Blog notes: getting Switch running on Windows with two AI vendors

Raw material for the Best Blog side track. Chronological, with the fix for each wall we hit. Day 1, Nov 4 2026.

## Goal
Run Vegapunk's satellites as Switch agents on one Windows 11 laptop: Claude Code (Claude Pro) and Antigravity (Gemini), in the same rooms.

## The walls, in order

1. **"Antigravity: Not installed" while Antigravity was installed.**
   Console doesn't look for the `agy` CLI. It needs `antigravity-acp`, a separate Google ACP server with its own sign-in, and Switch's install script only ships it for macOS (Apple Silicon) and Linux. Console's code even rejects `agy` as "the old Antigravity CLI".
   Fix: run it in Ubuntu on WSL2.

2. **Docs said Windows can't run agents locally.**
   `console/docs/sdk-sessions.md` says local Windows execution is unavailable. In practice Console 0.40.1 runs Claude Code on Windows fine through its managed agent controller. Lesson: test before trusting docs.

3. **Preparing Ubuntu as an SSH host.**
   Ubuntu's apt Node is too old (sidecar needs 20.3+): installed Node 22 from nodejs.org (checksum verified). Installed `openssh-server` on port 2222 (keys only), `unzip`, `tmux`, Claude Code, `antigravity-acp`. Put `~/.local/bin` on PATH at the top of `.bashrc` so non-interactive SSH sees it.

4. **`antigravity-acp: command not found`.**
   WSL's default user was root; everything was installed for `srinjoy`. Fix: always `wsl -d Ubuntu -u srinjoy`.

5. **False "CLI not installed" in Console's host page.**
   Bug in Console: the provider readiness probe calls `resolveCommandPath` without the target platform, so a Windows Console runs `where` (Windows) on a Linux host. The green "Installed" badge from the other checker was right. Worth an issue upstream.

6. **Ubuntu host never offered as a run location.**
   Console only allows remote run locations for a server that is not "local to this computer" (`new-agent-form.tsx`, `allowedHosts`). Pointing an "existing server" connection at the local server didn't work either: the native local server changes ports on every restart (3137, then 3678).
   Fix: let Console run the Switch server on the Ubuntu host itself ("Run or join a server on a remote host"). It bridges the ports back to Windows over SSH, so Windows agents still work.

7. **"Docker is not running" on the host.**
   Docker was running; the user just wasn't in the `docker` group. Added it, then had to kill the old SSH session because Console reused a connection opened before the group change.

8. **"Port 10957 is already in use on this computer".**
   Earlier we had switched WSL to mirrored networking (so Ubuntu could reach a Windows-hosted server). Mirrored mode also publishes Ubuntu's container ports on Windows, which collides with Console's own SSH port bridge. `ignoredPorts` did not help.
   Fix: drop mirrored mode, set `localhostForwarding=false`, and reach sshd through stdio instead of the network:
   `ProxyCommand C:\Windows\System32\wsl.exe -d Ubuntu -u srinjoy -- nc 127.0.0.1 2222`

9. **Result.** Server "Egghead" in Docker on Ubuntu; `claude-code.shaka.srinjoy` answering from Windows, `antigravity.lilith.srinjoy` answering from Linux (Gemini), same server, same rooms.

10. **Slack: "what do I do here?"**
    Creating a Slack workspace is not the same as creating the Slack *app*. The app is made at api.slack.com/apps from Switch's manifest (saved as `docs/slack-app-manifest.json`), then you need two tokens: an app-level `xapp-` token with `connections:write` (Socket Mode, so no public URL) and the `xoxb-` bot token from installing the app. Discord was simpler: bot token, two intents, an invite link and the server id.

11. **Rooms in two apps.** One Console form per room: pick the messaging app, name it, add agents. `#egghead-lab` exists in both Discord and Slack with Shaka (Claude, Windows) and Lilith (Gemini, Linux) in it. In Slack the channel was created private and didn't appear in the sidebar until opened via Console's room Configuration → Open in Slack. Both agents answered in both apps: Shaka "Windows 11", Lilith "Ubuntu 24.04 LTS (Linux 5.15 on WSL2)".

## Building Vegapunk: walls on day 1 (afternoon)

12. **A custom agent registered with the server's token belongs to "Agent Bootstrap", not you.** Punk Records registered fine (`POST /agents`, `always_on`), but its owner was a system user, so satellites set to "Me and my agents" would have refused it. Fix: each satellite's "Who can talk to your agent" became a custom rule naming `punk-records`. Lesson: addressing policies are real access control, and they bit us.

13. **Console dropdowns overlay the toggles under them.** While editing Lilith's rule, a click landed on "Bypass permissions" and "Can manage agents" and saved them on. Caught it from a screenshot, turned both off and saved. Lesson for the post: always screenshot before clicking near security toggles, and check an agent's settings after editing them.

14. **Agent operations and the connection header.** Sending `X-Switch-Connection-Id` without an open event stream is a 409 ("connection is not open"). Only send it while the stream is live; room-scoped calls take `room_id` instead.

15. **Testcontainers inside a sandbox.** switch-core's tests start Postgres with testcontainers, which needs the Docker socket; giving untrusted PR code the Docker socket would defeat the sandbox. Fix: a 30-line pytest plugin (`-p pg_redirect`) replaces `PostgresContainer` before conftest imports it and points it at a throwaway Postgres on an `--internal` Docker network. The test container itself has no internet, no capabilities and a read-only root.

16. **pytest stops at the first collection error.** On the base commit, a PR's new test file can't import the new module, and pytest aborted the whole run, so the other files never ran. `--continue-on-collection-errors` fixed it; an uncollectable file counts as "failed before", which is exactly what proves a new feature.

17. **Older branches, older locks.** One PR's lockfile predates `pytest-timeout`, so our `--timeout` flag crashed pytest and the PR looked "Unreproducible". Dropped the flag; the container's own time limit bounds the run. It flipped to Proven (39 proving tests).

18. **Merge commits hide the base.** Most merged PRs here used merge commits, so a PR's head is already in main and "merge base with main" is the head itself. Edison now finds the merge commit and uses its first parent.

19. **No history to backtest against.** Across 1,268 PRs, only 26 merged PRs ever linked an issue, and every issue with competing PRs is a hackathon issue still open. So the backtest became merge prediction (do proven PRs get merged more?), and the competing-PR question moved to the sealed prediction.

20. **GitHub refuses huge diffs** (406). The client now treats that as "no diff" instead of crashing.

21. **Windows writing into WSL.** One of the two leading backslashes of the `\\wsl.localhost\...` path got lost on the way into `.env`, and files went to `C:\wsl.localhost\...` instead (forward slashes `//wsl.localhost/Ubuntu/...` work in Python). Files written into WSL from Windows are owned by root; Punk Records now `chown`s each satellite's case folder so it can write its verdict.

22. **First live loop.** Punk Records created a private Discord room through `create_room`, mentioned Shaka, and read back "ACK" via `read_context` 24 seconds later: a custom protocol client driving a Claude Code agent through Switch.

23. **Unattended agents stall on approvals.** The first tribunals never finished. Shaka's file write failed with a ZodError inside Console's permission bridge (`updatedInput: expected record`), so it retried with PowerShell, which waits for a human to click Allow in the Discord thread. Lilith waited on an approval to open the case file. Agents can't send room commands (`!interrupt` from an agent is ignored), and a session stuck on an approval blocks every later mention in that room.

24. **Fix: make the room the workspace.** Punk Records now holds a live connection to the tribunal room (the stream claims it) and attaches the case file, both role briefs and every diff as **room documents** (`create_room_document`, 1 MiB max). Satellites read them with Switch's own document tool, which needs no approval. That's also more Switch-native: the evidence lives in the room's shared context, not on someone's disk.

25. **Fix 2: every document must fit in one read.** Shaka loaded all six documents at once (345,000 characters), blew its tool-result limit, and delegated to a subagent that tried to page the result with a shell command: another approval. Diffs are now split at file boundaries into ~40,000-character parts (lockfiles dropped), and the brief says "one document per call, no shell, no subagents". A stuck room is abandoned with `--fresh`, which archives it and opens a new one (new room = new agent sessions).

26. **The planted-defect harness caught Edison cheating itself.** We replaced every test body in a proven PR with `pass`, and Edison still said "Proven" (38 tests!). The hollow tests still import the PR's new module, so on the base commit they fail to collect, and Edison counted "uncollectable before" as "failed before". Fix: Edison now reads each test's AST and refuses to count a test that asserts nothing (no `assert`, no `pytest.raises`, no `assert_*`/`expect` call) as proof. Re-judging is free: it only needs the test source (`git show`) and the runs already cached. On real PRs it found a handful of assertion-free tests (#1276, #269, #412, #505, #652). After the fix: implementation removed, tests hollowed, tests skipped = 12/12 caught.

27. **Two harness bugs worth admitting.** Inserting `import pytest` above `from __future__ import annotations` is a SyntaxError, so "skipped" variants looked "Broken" for the wrong reason; and a variant of an already-merged PR inherited the wrong base. Both fixed; variants now record their original base in `refs/vegapunk/base/...`.

28. **Blind secret test.** A synthetic tribunal pitted #1153 against its twin with a fake AWS key and GitHub token appended (same title, made-up PR number). Shaka, the *spec* judge, flagged it high on its own: "fake credential strings named _PLANTED_AWS_KEY and _PLANTED_GH_TOKEN ... would trigger secret scanning". Edison, by design, can't see it.

29. **Antigravity explores before it works.** On a fresh session Lilith ran `ls` on her own MCP tool folder to discover her tools, which is a shell command, which waits for an approval. Fix: Punk Records posts every document id right after the kickoff, and the brief says "call `load_internal_documents` with these ids; don't list directories".

30. **Backtest.** 40 past PRs (20 merged, 20 closed unmerged): Proven PRs were merged 58% of the time, Broken 17%, Unproven 0%. AUC 0.79 for Edison + Atlas as a merge predictor. Some closed PRs were proven but superseded, so it's a floor.

31. **A memory budget is a design constraint.** WSL had 8 GB. Two Edison jobs are cheap (~400 MB each); seven idle Antigravity sessions (one per room Lilith was ever in) were ~1.1 GB; a pnpm install of the Console workspace beside them got OOM-killed (load average 462). TypeScript proofs now run after the Python batch, one job at a time, and a failed sandbox build is never cached as "Unreproducible".

32. **One connection, one room.** The first batch of council tribunals died after the first issue: "This connection covers several rooms; the operation needs one". Room-scoped operations like `create_room_document` resolve their room from the connection, and Punk Records had kept claiming rooms on the same connection id. Now each `attach()` opens a fresh `scope=single` connection and retires the old one (it stops being heartbeated, gets swept, and its reader thread exits).

## Good moments for the post
- Lilith (the "evil" satellite) asked to dump environment variables on her first run; we denied it in Console's approval card. A nice real example of why per-action approval matters.
- Two model vendors in one room on a single laptop, no paid API.

## Settings that ended up mattering
- `.wslconfig`: `memory=8GB`, `localhostForwarding=false`
- `~/.ssh/config` host `wsl-switch` with the ProxyCommand above
- Ubuntu: user in `docker` group; sshd on 2222 keys only; Node 22; `antigravity-acp --login` and `claude` login done as the same user Console uses
- After reboot: start WSL (`wsl -d Ubuntu -u srinjoy`), then open Console; Egghead containers have no restart policy
