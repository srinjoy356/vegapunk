"""Run the council over many issues, most contested first, then refresh the report.

    uv run python -m vegapunk.council --top 8              # 8 most contested issues Edison has finished
    uv run python -m vegapunk.council --issues 803 771

Tribunals use Claude (Shaka) and Gemini (Lilith) subscriptions, which have usage limits,
so they run one at a time and only where Edison has proved every PR; issues without a
tribunal are still ranked on the deterministic evidence.
"""

import argparse
import json
from pathlib import Path

from vegapunk import pythagoras, report, results
from vegapunk.github import load_env
from vegapunk.switch import Agent
from vegapunk.tribunal import run as run_tribunal

CACHE = Path("cache")


def ready(issue: int, numbers: list[int]) -> bool:
    return len(numbers) > 1 and all((CACHE / "edison" / f"pr-{n}.json").exists() for n in numbers)


def pending(top: int) -> list[int]:
    index = json.loads((CACHE / "index.json").read_text(encoding="utf-8"))["issues"]
    done = {int(p.parent.name) for p in (CACHE / "tribunal").glob("*/verdicts.json")
            if len(json.loads(p.read_text(encoding="utf-8"))) >= 2}
    candidates = [int(n) for n, prs in index.items() if ready(int(n), prs) and int(n) not in done]
    return sorted(candidates, key=lambda n: -len(index[str(n)]))[:top]


def main() -> None:
    load_env()
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--top", type=int, default=5)
    ap.add_argument("--issues", type=int, nargs="*")
    ap.add_argument("--bridge", default=None)
    ap.add_argument("--timeout", type=int, default=50 * 60)
    args = ap.parse_args()
    import os
    bridge = args.bridge or os.environ.get("TRIBUNAL_BRIDGE", "discord")
    agent = Agent.from_env()
    for n in args.issues or pending(args.top):
        print(f"== tribunal #{n}", flush=True)
        pythagoras.run(n)
        try:
            run_tribunal(agent, n, bridge, args.timeout)
        except Exception as e:  # one bad issue must not stop the rest
            print(f"#{n}: {e}", flush=True)
    print(report.render(), flush=True)
    results.main()


if __name__ == "__main__":
    main()
