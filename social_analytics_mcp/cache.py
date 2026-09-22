"""Caches backing one MCP server session, optionally shared across instances."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from threading import RLock
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CacheLookup:
    value: dict[str, Any]
    hit: bool


class SessionProfileCache:
    """Caches a public profile once per running server process.

    The source actor returns the current profile and its latest posts, so a
    username-only cache safely also satisfies repeated date-range requests.
    """

    def __init__(self, ttl_seconds: int = 900, backend: GcsCacheBackend | None = None) -> None:
        self._items: dict[str, tuple[datetime, dict[str, Any]]] = {}
        self._ttl = timedelta(seconds=ttl_seconds)
        self._ttl_seconds = ttl_seconds
        self._backend = backend
        self._lock = RLock()

    def get(self, username: str) -> CacheLookup | None:
        with self._lock:
            entry = self._items.get(username)
            if entry is not None:
                stored_at, value = entry
                if datetime.now(timezone.utc) - stored_at <= self._ttl:
                    return CacheLookup(value=value, hit=True)
                del self._items[username]

        if self._backend is None:
            return None
        shared = self._backend.read(username)
        if shared is None:
            return None
        # Promote a shared hit into this process so repeat calls skip the network.
        with self._lock:
            self._items[username] = (datetime.now(timezone.utc), shared)
        return CacheLookup(value=shared, hit=True)

    def put(self, username: str, profile: dict[str, Any]) -> CacheLookup:
        with self._lock:
            self._items[username] = (datetime.now(timezone.utc), profile)
        if self._backend is not None:
            self._backend.write(username, profile, self._ttl_seconds)
        return CacheLookup(value=profile, hit=False)

    def clear(self) -> None:
        with self._lock:
            self._items.clear()


class GcsCacheBackend:
    """Stores cache entries as JSON objects so every Cloud Run instance shares them.

    A Cloud Run service scales to many instances and recycles them freely, so an
    in-process cache is cold far more often than not. Every miss costs a 30-90s
    Apify run, which dwarfs the ~50-100ms this backend adds.
    """

    def __init__(self, bucket_name: str, prefix: str = "cache", client: Any | None = None) -> None:
        self._bucket_name = bucket_name
        self._prefix = prefix.strip("/")
        self._client = client
        self._bucket: Any | None = None
        self._lock = RLock()

    def _get_bucket(self) -> Any | None:
        with self._lock:
            if self._bucket is not None:
                return self._bucket
            try:
                if self._client is None:
                    from google.cloud import storage

                    self._client = storage.Client()
                self._bucket = self._client.bucket(self._bucket_name)
            except Exception as exc:
                logger.warning("Shared cache unavailable, falling back to memory: %s", exc)
                return None
            return self._bucket

    def _blob_name(self, key: str) -> str:
        # Cache keys carry ':' and full URLs, which are not safe object names.
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
        return f"{self._prefix}/{digest}.json"

    def read(self, key: str) -> dict[str, Any] | None:
        bucket = self._get_bucket()
        if bucket is None:
            return None
        try:
            blob = bucket.blob(self._blob_name(key))
            raw = blob.download_as_bytes()
        except Exception:
            # A miss and a transport error are both simply "no cached value".
            return None
        try:
            entry = json.loads(raw)
        except json.JSONDecodeError:
            return None
        if float(entry.get("expires_at", 0)) <= time.time():
            return None
        value = entry.get("value")
        return value if isinstance(value, dict) else None

    def write(self, key: str, value: dict[str, Any], ttl_seconds: int) -> None:
        bucket = self._get_bucket()
        if bucket is None:
            return
        entry = {"key": key, "expires_at": time.time() + ttl_seconds, "value": value}
        try:
            blob = bucket.blob(self._blob_name(key))
            blob.upload_from_string(json.dumps(entry, default=str), content_type="application/json")
        except Exception as exc:
            # A cache write must never fail the tool call that produced the data.
            logger.warning("Shared cache write failed for %s: %s", key, exc)


def build_cache_backend() -> GcsCacheBackend | None:
    """Return a shared backend when one is configured, else None for memory-only."""
    if os.getenv("CACHE_BACKEND", "memory").strip().lower() != "gcs":
        return None
    bucket = os.getenv("CACHE_BUCKET", "").strip()
    if not bucket:
        logger.warning("CACHE_BACKEND=gcs but CACHE_BUCKET is unset; using memory only.")
        return None
    return GcsCacheBackend(bucket, prefix=os.getenv("CACHE_PREFIX", "cache"))


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
