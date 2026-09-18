"""Usage tracking and structured telemetry for the MCP server."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
import json
import sys
from threading import RLock
import time
from typing import Any


class UsageTracker:
    """Thread-safe in-memory usage metrics and structured logging."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._start_time = time.time()
        self._total_invocations = 0
        self._tool_counts: dict[str, int] = defaultdict(int)
        self._unique_clients: set[str] = set()
        self._unique_usernames: set[str] = set()
        self._error_counts: dict[str, int] = defaultdict(int)

    def record_call(
        self,
        tool_name: str,
        params: dict[str, Any],
        ok: bool,
        duration_ms: float,
        client_id: str | None = None,
        error_message: str | None = None,
    ) -> None:
        with self._lock:
            self._total_invocations += 1
            self._tool_counts[tool_name] += 1
            if client_id:
                self._unique_clients.add(client_id)
            username = params.get("username")
            if username:
                self._unique_usernames.add(str(username).lower().lstrip("@"))
            if not ok and error_message:
                self._error_counts[tool_name] += 1

        # Emit structured log for Google Cloud Logging
        log_entry = {
            "severity": "INFO" if ok else "WARNING",
            "event": "mcp_tool_invocation",
            "tool": tool_name,
            "ok": ok,
            "duration_ms": round(duration_ms, 2),
            "client_id": client_id or "anonymous",
            "username_queried": params.get("username"),
            "params": {k: v for k, v in params.items() if k != "username"},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        if error_message:
            log_entry["error"] = error_message

        try:
            sys.stdout.write(json.dumps(log_entry) + "\n")
            sys.stdout.flush()
        except Exception:
            pass

    def get_metrics(self) -> dict[str, Any]:
        with self._lock:
            uptime = round(time.time() - self._start_time, 1)
            return {
                "ok": True,
                "uptime_seconds": uptime,
                "total_invocations": self._total_invocations,
                "unique_clients_count": len(self._unique_clients),
                "unique_instagram_targets_count": len(self._unique_usernames),
                "tool_invocations": dict(self._tool_counts),
                "errors_by_tool": dict(self._error_counts),
                "recent_instagram_targets": list(self._unique_usernames)[-10:],
            }


tracker = UsageTracker()
