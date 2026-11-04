# Runbook

Everything is cached, so each step only does new work (new PRs, new commits on existing PRs).

## Every few hours until Nov 7

Windows, in `C:\dev\switch`:
```bash
uv run python -m vegapunk.ingest
```

Ubuntu (WSL), with Switch Console open:
```bash
export PATH=$HOME/.local/bin:$PATH UV_PROJECT_ENVIRONMENT=$HOME/vegapunk-work/venv
cd /mnt/c/dev/switch
uv run python -m vegapunk.edison --all --atlas --jobs 2       # new PRs: proofs + static checks
uv run python -m vegapunk.edison --all --matrix --jobs 2      # cross matrices for issues with new PRs
uv run python -m vegapunk.edison --all --ts --jobs 1          # Console vitest proofs (needs ~3 GB free)
```

Windows again:
```bash
uv run python -m vegapunk.council --top 5      # tribunals for the most contested issues not yet judged
uv run python -m vegapunk.tribunal docket      # refresh the Discord docket
uv run python -m vegapunk.tribunal watch       # leave running: records Stella's `pick #N because ...`
```

## Nov 7, evening (before the 23:59 IST submission)

1. Run the "every few hours" steps one last time.
2. Seal:
   ```bash
   uv run python -m vegapunk.seal seal
   ```
   It prints the SHA-256 and writes `predictions/<stamp>.sha256`. Commit that file and post the hash (#HowISwitch). Keep `cache/predictions/rankings-<stamp>.json` private.
3. `uv run python -m vegapunk.report` and `uv run python -m vegapunk.results`, then record the demo.

## After the maintainers choose

```bash
uv run python -m vegapunk.ingest
uv run python -m vegapunk.seal reveal cache/predictions/rankings-<stamp>.json
```
It refuses if the file's hash doesn't match the sealed one, then scores top-1 / top-3 against the PRs actually merged and publishes the rankings and the score in `predictions/`.

## When something sticks

- **A tribunal gets no verdict**: a satellite is usually waiting on an approval in the Discord thread. Deny it there, or reopen in a new room: `uv run python -m vegapunk.tribunal run <issue> --fresh`.
- **Lilith never starts**: Antigravity (Gemini) may be rate-limited; tribunals still finish with Shaka plus the deterministic evidence.
- **After a reboot**: `wsl -d Ubuntu -u srinjoy` (keep it open), open Switch Console, start Egghead if it shows stopped.
- **WSL out of memory** (load average in the hundreds): run Edison with `--jobs 1`, and close stale tribunal rooms' sessions.
