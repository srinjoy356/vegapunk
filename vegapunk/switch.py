"""Switch agent-protocol client: registration, operations, messages and the event stream.

Implements the wire contract from Switch's docs (internals/agent-protocol): one SSE
stream down, HTTP calls up, a heartbeat every 2 seconds, and a client-generated
connection id that survives reconnects.
"""

import json
import os
import threading
import time
import uuid
from collections.abc import Iterator
from pathlib import Path

import httpx

from vegapunk.github import load_env

ENV = Path(".env")


def save_env(updates: dict[str, str], path: Path = ENV) -> None:
    """Set KEY=VALUE lines in .env, replacing existing keys and keeping everything else."""
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    lines = [l for l in lines if l.split("=", 1)[0].strip() not in updates]
    lines += [f"{k}={v}" for k, v in updates.items()]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    os.environ.update(updates)


def register(name: str, description: str, base_url: str | None = None, overwrite: bool = False) -> tuple[str, str]:
    """Register an always-on custom agent with the server's registration token. Returns (id, api_key)."""
    load_env()
    base_url = base_url or os.environ["SWITCH_API_URL"]
    r = httpx.post(
        f"{base_url}/agents",
        headers={"Authorization": f"Bearer {os.environ['SWITCH_REGISTRATION_TOKEN']}"},
        json={
            "name": name,
            "description": description,
            "connector_type": "custom",
            "integration_profile": {
                "connection_model": "always_on",
                "message_exchange": True,
                "pre_invocation_mediation": [],
                "post_invocation_mediation": [],
                "event_reporting": [],
            },
            "overwrite": overwrite,
        },
        timeout=30,
    )
    r.raise_for_status()
    body = r.json()
    return body["id"], body["api_key"]


class Agent:
    """One registered agent talking to the agent bridge."""

    def __init__(self, agent_id: str, api_key: str, base_url: str):
        self.id = agent_id
        self.connection_id = str(uuid.uuid4())
        self.http = httpx.Client(base_url=base_url, headers={"Authorization": f"Bearer {api_key}"}, timeout=60)
        self.cursor: int | None = None
        self._beating = threading.Event()

    @classmethod
    def from_env(cls, prefix: str = "PUNK_RECORDS") -> "Agent":
        load_env()
        return cls(os.environ[f"{prefix}_AGENT_ID"], os.environ[f"{prefix}_API_KEY"], os.environ["SWITCH_API_URL"])

    # Operations -----------------------------------------------------------

    def ops(self) -> dict:
        r = self.http.get(f"/agents/{self.id}/ops")
        r.raise_for_status()
        return r.json()["operations"]

    def op(self, _operation: str, /, **args):
        """Invoke an operation; arguments go unwrapped in the body (positional-only so `name=` can be an argument)."""
        # the header binds the call to a live connection; sending it without an open stream is a 409.
        # The stream can drop and reopen at any moment, so retry once, then try without the header
        # (calls that name their room_id don't need the connection at all).
        url = f"/agents/{self.id}/ops/{_operation}"
        attempts = [{"X-Switch-Connection-Id": self.connection_id}] * 2 + [{}] if self._beating.is_set() else [{}]
        for i, headers in enumerate(attempts):
            r = self._post(url, args, headers)
            if not (r.status_code == 409 and headers and "not open" in r.text):
                break
            time.sleep(3 if i == 0 else 0)
        if r.status_code >= 400:
            raise RuntimeError(f"{_operation} -> {r.status_code}: {r.text[:500]}")
        return r.json()["result"]

    def _post(self, url: str, body: dict, headers: dict | None = None, attempts: int = 4) -> httpx.Response:
        """POST with retries on dropped connections (the bridge is reached through an SSH tunnel)."""
        for attempt in range(attempts):
            try:
                return self.http.post(url, json=body, headers=headers or {})
            except httpx.TransportError:
                if attempt == attempts - 1:
                    raise
                time.sleep(2 ** attempt)

    def say(self, room_id: str, content: str) -> None:
        """Post into a room without needing a live connection."""
        r = self._post(f"/agents/{self.id}/message", {"room_id": room_id, "content": content})
        if r.status_code >= 400:
            raise RuntimeError(f"message -> {r.status_code}: {r.text[:500]}")

    # Event stream ---------------------------------------------------------

    def _heartbeat(self) -> None:
        while self._beating.is_set():
            try:
                r = self.http.post(f"/agents/{self.id}/connection/beat",
                                   json={"connection_id": self.connection_id, "cursor": self.cursor or 0})
                if r.status_code in (404, 409):  # connection dead or no stream: the reader reopens it
                    pass
            except httpx.HTTPError:
                pass
            time.sleep(2)

    def attach(self, room_id: str, timeout: float = 20) -> None:
        """Hold a live single-room connection that claims `room_id`, so room-scoped operations
        (create_room_document, post_message, ...) resolve to it. Each call retires the previous
        attachment: a connection covering several rooms makes those operations ambiguous (400).
        Events are drained in a thread."""
        ready = threading.Event()
        if getattr(self, "_stop", None):
            self._stop.set()  # the old stream ends once its connection stops being beaten and is swept
        self._stop = stop = threading.Event()
        self.connection_id, self.cursor = str(uuid.uuid4()), None
        cid = self.connection_id

        def drain():
            for _ in self.events(rooms=[room_id], on_state=ready.set, scope="single", stop=stop, connection_id=cid):
                pass

        threading.Thread(target=drain, daemon=True).start()
        if not ready.wait(timeout):
            raise RuntimeError(f"no connection_state from the event stream within {timeout}s")

    def events(self, rooms: list[str] | None = None, on_state=None, scope: str = "all",
               stop: threading.Event | None = None, connection_id: str | None = None) -> Iterator[dict]:
        """Yield domain events, reopening the stream with the same connection id on drops, until `stop` is set."""
        if not self._beating.is_set():
            self._beating.set()
            threading.Thread(target=self._heartbeat, daemon=True).start()
        cid = connection_id or self.connection_id
        cursor = None if connection_id else self.cursor  # each connection keeps its own read position
        while not (stop and stop.is_set()):
            params = {"connection_id": cid, "scope": scope, "filter": "all",
                      "start_from": "head" if cursor is None else str(cursor),
                      "client": "vegapunk-punk-records", "client_version": "0.1.0"}
            if rooms:
                params["rooms"] = ",".join(rooms)
            headers = {"Accept": "text/event-stream"}
            if cursor is not None:
                headers["Last-Event-ID"] = str(cursor)
            try:
                with self.http.stream("GET", f"/agents/{self.id}/events", params=params, headers=headers,
                                      timeout=httpx.Timeout(60, read=None)) as r:
                    r.raise_for_status()
                    for frame in parse_sse(r.iter_lines()):
                        if stop and stop.is_set():
                            return
                        if frame.get("id"):
                            cursor = int(frame["id"])
                            if cid == self.connection_id:
                                self.cursor = cursor  # what the heartbeat reports
                        if frame.get("event") == "connection_state" and on_state:
                            on_state()
                        data = frame.get("data")
                        if data:
                            yield json.loads(data) | {"_event": frame.get("event")}
            except (httpx.HTTPError, json.JSONDecodeError):
                time.sleep(2)


def parse_sse(lines) -> Iterator[dict]:
    """Group SSE lines into frames: {'id', 'event', 'data'}. Comment lines (keepalives) are skipped."""
    frame: dict[str, str] = {}
    for line in lines:
        if not line:
            if frame:
                yield frame
                frame = {}
            continue
        if line.startswith(":"):
            continue
        key, _, value = line.partition(":")
        value = value.removeprefix(" ")
        frame[key] = frame[key] + "\n" + value if key == "data" and key in frame else value
    if frame:
        yield frame
