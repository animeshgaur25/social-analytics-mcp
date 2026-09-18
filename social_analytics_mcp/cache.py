"""Small in-process stores used for one MCP server session."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from threading import RLock
from typing import Any


@dataclass(frozen=True)
class CacheLookup:
    value: dict[str, Any]
    hit: bool


class SessionProfileCache:
    """Caches a public profile once per running server process.

    The source actor returns the current profile and its latest posts, so a
    username-only cache safely also satisfies repeated date-range requests.
    """

    def __init__(self, ttl_seconds: int = 900) -> None:
        self._items: dict[str, tuple[datetime, dict[str, Any]]] = {}
        self._ttl = timedelta(seconds=ttl_seconds)
        self._lock = RLock()

    def get(self, username: str) -> CacheLookup | None:
        with self._lock:
            entry = self._items.get(username)
            if entry is None:
                return None
            stored_at, value = entry
            if datetime.now(timezone.utc) - stored_at > self._ttl:
                del self._items[username]
                return None
            return CacheLookup(value=value, hit=True)

    def put(self, username: str, profile: dict[str, Any]) -> CacheLookup:
        with self._lock:
            self._items[username] = (datetime.now(timezone.utc), profile)
        return CacheLookup(value=profile, hit=False)

    def clear(self) -> None:
        with self._lock:
            self._items.clear()


class FollowerHistory:
    """Keeps fresh follower snapshots observed during the current session."""

    def __init__(self) -> None:
        self._snapshots: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self._lock = RLock()

    def record(self, username: str, followers: int, observed_at: datetime | None = None) -> None:
        snapshot = {
            "timestamp": (observed_at or datetime.now(timezone.utc)).isoformat(),
            "followers": followers,
        }
        with self._lock:
            snapshots = self._snapshots[username]
            snapshots.append(snapshot)

    def get(self, username: str) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._snapshots.get(username, []))
