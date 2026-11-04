"""Thin GitHub client: GraphQL for bulk metadata, REST for diffs."""

import os
import time
from pathlib import Path

import httpx

API = "https://api.github.com"


def load_env(path: Path = Path(".env")) -> None:
    """Load KEY=VALUE lines into os.environ without overriding what is already set."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("'\""))


class GitHub:
    def __init__(self, token: str | None = None):
        load_env()
        token = token or os.environ.get("GITHUB_TOKEN")
        if not token:
            raise SystemExit("GITHUB_TOKEN is not set (put it in .env)")
        self.http = httpx.Client(
            base_url=API,
            headers={"Authorization": f"Bearer {token}", "User-Agent": "vegapunk"},
            timeout=60,
        )
        self.remaining: str | None = None

    def _request(self, method: str, url: str, attempts: int = 4, **kwargs) -> httpx.Response:
        """Retry dropped connections and 5xx with backoff; GitHub does both under load."""
        for attempt in range(attempts):
            try:
                r = self.http.request(method, url, **kwargs)
                if r.status_code < 500:
                    self.remaining = r.headers.get("x-ratelimit-remaining", self.remaining)
                    r.raise_for_status()
                    return r
            except httpx.TransportError:
                if attempt == attempts - 1:
                    raise
            time.sleep(2 ** attempt)
        r.raise_for_status()
        return r

    def graphql(self, query: str, **variables) -> dict:
        r = self._request("POST", "/graphql", json={"query": query, "variables": variables})
        body = r.json()
        if body.get("errors"):
            raise RuntimeError(f"GraphQL errors: {body['errors']}")
        return body["data"]

    def diff(self, owner: str, repo: str, number: int) -> str:
        """The PR's unified diff, or "" when GitHub refuses it as too large (406)."""
        try:
            r = self._request(
                "GET", f"/repos/{owner}/{repo}/pulls/{number}",
                headers={"Accept": "application/vnd.github.diff"},
            )
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 406:
                return ""
            raise
        return r.text
