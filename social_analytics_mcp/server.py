"""MCP server definition using the official Python MCP SDK."""

from __future__ import annotations

import asyncio
import os
import time
from typing import Any

from dotenv import load_dotenv
from mcp.server.fastmcp import Context, FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse

from .tools import SocialAnalyticsTools
from .usage import tracker

load_dotenv()

mcp = FastMCP(
    "social-analytics-mcp",
    instructions=(
        "Analyse public Instagram profiles with Apify data. Use list_available_metrics before "
        "selecting a dashboard metric. Chart responses contain a PNG as base64 and an interactive Plotly spec."
    ),
    # stdio ignores these settings. Cloud Run uses the HTTP transport below and
    # requires a process that binds to $PORT on all container interfaces.
    host=os.getenv("MCP_HOST", "127.0.0.1"),
    port=int(os.getenv("PORT", os.getenv("MCP_PORT", "8000"))),
    streamable_http_path=os.getenv("MCP_HTTP_PATH", "/mcp"),
)
tools = SocialAnalyticsTools()


@mcp.custom_route("/health", methods=["GET"])
async def health_check(request: Request) -> JSONResponse:
    """Simple healthcheck endpoint for Cloud Run and uptime monitors."""
    return JSONResponse({"status": "healthy", "service": "social-analytics-mcp"})


@mcp.custom_route("/stats", methods=["GET"])
async def stats_endpoint(request: Request) -> JSONResponse:
    """Public HTTP telemetry endpoint to inspect user count and tool usage metrics."""
    return JSONResponse(tracker.get_metrics())


@mcp.tool()
async def get_profile_summary(username: str, ctx: Context | None = None) -> dict:
    """Return public profile bio and headline counts for an Instagram username."""
    start = time.monotonic()
    client_id = getattr(ctx, "client_id", None) if ctx else None
    result = await asyncio.to_thread(tools.get_profile_summary, username)
    duration_ms = (time.monotonic() - start) * 1000
    tracker.record_call(
        "get_profile_summary",
        {"username": username},
        bool(result.get("ok")),
        duration_ms,
        client_id=client_id,
        error_message=result.get("error", {}).get("message"),
    )
    return result


@mcp.tool()
async def get_engagement_metrics(
    username: str,
    date_range: str | None = None,
    post_limit: int = 12,
    ctx: Context | None = None,
) -> dict:
    """Return per-post likes, comments, media type, and engagement rates.

    date_range accepts all, a trailing day range such as 30d, or an inclusive
    ISO range such as 2026-01-01:2026-01-31.
    """
    start = time.monotonic()
    client_id = getattr(ctx, "client_id", None) if ctx else None
    result = await asyncio.to_thread(tools.get_engagement_metrics, username, date_range, post_limit)
    duration_ms = (time.monotonic() - start) * 1000
    tracker.record_call(
        "get_engagement_metrics",
        {"username": username, "date_range": date_range, "post_limit": post_limit},
        bool(result.get("ok")),
        duration_ms,
        client_id=client_id,
        error_message=result.get("error", {}).get("message"),
    )
    return result


@mcp.tool()
async def generate_dashboard(
    username: str,
    metric: str,
    chart_type: str | None = None,
    date_range: str | None = None,
    top_n: int = 5,
    ctx: Context | None = None,
) -> dict:
    """Generate a light-theme social-performance dashboard for a public profile.

    metric: follower_growth, engagement_rate_over_time,
    top_posts_by_engagement, or content_type_comparison. chart_type may be line
    or bar; omitted selects the most appropriate chart. The response contains
    a base64 PNG and an interactive Plotly JSON specification.
    """
    start = time.monotonic()
    client_id = getattr(ctx, "client_id", None) if ctx else None
    result = await asyncio.to_thread(
        tools.generate_dashboard, username, metric, chart_type, date_range, top_n
    )
    duration_ms = (time.monotonic() - start) * 1000
    tracker.record_call(
        "generate_dashboard",
        {"username": username, "metric": metric, "chart_type": chart_type, "date_range": date_range},
        bool(result.get("ok")),
        duration_ms,
        client_id=client_id,
        error_message=result.get("error", {}).get("message"),
    )
    return result


@mcp.tool()
def list_available_metrics(ctx: Context | None = None) -> dict:
    """List supported Instagram dashboard metrics, chart types, and data limits."""
    start = time.monotonic()
    client_id = getattr(ctx, "client_id", None) if ctx else None
    result = tools.list_available_metrics()
    duration_ms = (time.monotonic() - start) * 1000
    tracker.record_call(
        "list_available_metrics",
        {},
        bool(result.get("ok")),
        duration_ms,
        client_id=client_id,
    )
    return result


@mcp.tool()
def get_usage_metrics() -> dict:
    """Return live usage statistics, invocation counts, unique targets, and uptime."""
    return tracker.get_metrics()


def main() -> None:
    """Run as an MCP server with support for stdio or streamable-http transports."""
    mcp.run(transport=os.getenv("MCP_TRANSPORT", "stdio"))


if __name__ == "__main__":
    main()
