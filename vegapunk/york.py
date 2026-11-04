"""York: the only door to paid model calls. Logs every call and enforces a hard dollar cap.

Ledger: cache/york/ledger.jsonl, one line per call. When the next call could push spend
past YORK_CAP_USD (default 1.00), York refuses instead of calling, and the caller falls
back to its deterministic path.
"""

import json
import os
import time
from pathlib import Path

import httpx

from vegapunk.github import load_env

LEDGER = Path("cache/york/ledger.jsonl")
# USD per 1M tokens (input, output). shortcut: hand-copied from OpenAI's price list; update if the model or price changes
PRICES = {"gpt-4o-mini": (0.15, 0.60)}
# worst case for one call, so a call that starts under the cap cannot end far over it
MAX_OUTPUT_TOKENS = 800


class CapReached(RuntimeError):
    pass


def spent(ledger: Path = LEDGER) -> float:
    if not ledger.exists():
        return 0.0
    return round(sum(json.loads(l)["usd"] for l in ledger.read_text(encoding="utf-8").splitlines() if l), 6)


def cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    price_in, price_out = PRICES[model]
    return (prompt_tokens * price_in + completion_tokens * price_out) / 1_000_000


def chat(messages: list[dict], purpose: str, json_mode: bool = False, ledger: Path = LEDGER) -> str:
    """One chat completion through York. Raises CapReached instead of overspending."""
    load_env()
    model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
    cap = float(os.environ.get("YORK_CAP_USD", "1.00"))
    prompt_estimate = sum(len(m["content"]) for m in messages) // 3  # ~3 chars per token, deliberately high
    worst = cost(model, prompt_estimate, MAX_OUTPUT_TOKENS)
    if spent(ledger) + worst > cap:
        raise CapReached(f"York: ${spent(ledger):.4f} spent of ${cap:.2f}; refusing '{purpose}'")
    body = {"model": model, "messages": messages, "max_tokens": MAX_OUTPUT_TOKENS, "temperature": 0}
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    r = httpx.post("https://api.openai.com/v1/chat/completions", json=body, timeout=120,
                   headers={"Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}"})
    r.raise_for_status()
    data = r.json()
    usage = data["usage"]
    usd = cost(model, usage["prompt_tokens"], usage["completion_tokens"])
    ledger.parent.mkdir(parents=True, exist_ok=True)
    with ledger.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"at": time.time(), "purpose": purpose, "model": model, "usd": round(usd, 6),
                            "prompt_tokens": usage["prompt_tokens"],
                            "completion_tokens": usage["completion_tokens"]}) + "\n")
    return data["choices"][0]["message"]["content"]


def report(ledger: Path = LEDGER) -> dict:
    """Spend by purpose, for the docket and the README."""
    rows = [json.loads(l) for l in ledger.read_text(encoding="utf-8").splitlines() if l] if ledger.exists() else []
    by: dict[str, dict] = {}
    for r in rows:
        key = r["purpose"].split(":")[0]
        b = by.setdefault(key, {"calls": 0, "usd": 0.0, "tokens": 0})
        b["calls"] += 1
        b["usd"] = round(b["usd"] + r["usd"], 6)
        b["tokens"] += r["prompt_tokens"] + r["completion_tokens"]
    return {"spent_usd": spent(ledger), "cap_usd": float(os.environ.get("YORK_CAP_USD", "1.00")), "by_purpose": by}


if __name__ == "__main__":
    print(json.dumps(report(), indent=2))
