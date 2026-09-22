"""MCP server definition using the official Python MCP SDK."""

from __future__ import annotations

import asyncio
import os
import time
from typing import Any

from dotenv import load_dotenv
from mcp.server.fastmcp import Context, FastMCP
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse

from .tools import SocialAnalyticsTools
from .usage import tracker

load_dotenv()

mcp = FastMCP(
    "social-analytics-mcp",
    instructions=(
        "Analyse public Instagram profiles and YouTube channels with Apify data. Every tool takes "
        "platform='instagram' (default) or platform='youtube'; for YouTube pass a channel handle or "
        "URL such as '@MrBeast'. Use list_available_metrics before selecting a dashboard metric. "
        "Responses contain modern interactive Plotly charts, base64 PNGs, formatted Markdown data "
        "tables, and AI performance insights."
    ),
    # stdio ignores these settings. Cloud Run uses the HTTP transport below and
    # requires a process that binds to $PORT on all container interfaces.
    host=os.getenv("MCP_HOST", "127.0.0.1"),
    port=int(os.getenv("PORT", os.getenv("MCP_PORT", "8000"))),
    streamable_http_path=os.getenv("MCP_HTTP_PATH", "/mcp"),
)
tools = SocialAnalyticsTools()


@mcp.custom_route("/", methods=["GET"])
async def root_dashboard(request: Request) -> HTMLResponse:
    """Browser landing page displaying service status, live metrics, and client instructions."""
    metrics = tracker.get_metrics()
    invocations = metrics.get("total_invocations", 0)
    uptime = metrics.get("uptime_seconds", 0)
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Social Analytics MCP Server</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
  <style>
    :root {{
      --bg: #0b0f19;
      --card-bg: rgba(18, 24, 38, 0.85);
      --border: rgba(255, 255, 255, 0.08);
      --accent: #38bdf8;
      --accent-grad: linear-gradient(135deg, #38bdf8 0%, #818cf8 100%);
      --text: #f8fafc;
      --text-muted: #94a3b8;
      --green: #10b981;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: 'Plus Jakarta Sans', -apple-system, sans-serif;
      background: var(--bg);
      color: var(--text);
      min-height: 100vh;
      display: flex;
      flex-direction: column;
      align-items: center;
      padding: 40px 20px;
      line-height: 1.5;
    }}
    .container {{ max-width: 820px; width: 100%; }}
    .badge {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 4px 12px;
      background: rgba(16, 185, 129, 0.12);
      border: 1px solid rgba(16, 185, 129, 0.3);
      border-radius: 999px;
      color: var(--green);
      font-size: 12px;
      font-weight: 600;
      margin-bottom: 16px;
    }}
    .badge-dot {{ width: 8px; height: 8px; border-radius: 50%; background: var(--green); }}
    h1 {{
      font-size: 32px;
      font-weight: 700;
      background: var(--accent-grad);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      margin-bottom: 8px;
    }}
    p.lead {{ color: var(--text-muted); font-size: 16px; margin-bottom: 28px; }}
    .stats-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 16px;
      margin-bottom: 32px;
    }}
    .stat-card {{
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 14px;
      padding: 20px;
      backdrop-filter: blur(12px);
    }}
    .stat-label {{ font-size: 12px; color: var(--text-muted); text-transform: uppercase; font-weight: 600; letter-spacing: 0.5px; }}
    .stat-val {{ font-size: 26px; font-weight: 700; color: #ffffff; margin-top: 4px; }}
    .card {{
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 16px;
      padding: 28px;
      margin-bottom: 24px;
      backdrop-filter: blur(12px);
    }}
    h2 {{ font-size: 18px; font-weight: 600; margin-bottom: 14px; color: #ffffff; }}
    code, pre {{ font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; }}
    pre {{
      background: rgba(0, 0, 0, 0.45);
      border: 1px solid var(--border);
      padding: 16px;
      border-radius: 10px;
      overflow-x: auto;
      font-size: 13px;
      color: #38bdf8;
    }}
    .endpoint-list {{ list-style: none; display: flex; flex-direction: column; gap: 10px; }}
    .endpoint-item {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 12px 16px;
      background: rgba(255, 255, 255, 0.03);
      border: 1px solid var(--border);
      border-radius: 10px;
      font-size: 14px;
    }}
    .endpoint-item a {{ color: var(--accent); text-decoration: none; font-weight: 500; }}
    .endpoint-item a:hover {{ text-decoration: underline; }}
  </style>
</head>
<body>
  <div class="container">
    <div class="badge"><span class="badge-dot"></span> Live on Google Cloud Run</div>
    <h1>Social Analytics MCP Server</h1>
    <p class="lead">Interactive Model Context Protocol (MCP) server providing Instagram profile and YouTube channel analytics, automated charts, tables, and AI insights.</p>
    
    <div class="stats-grid">
      <div class="stat-card">
        <div class="stat-label">Total Invocations</div>
        <div class="stat-val">{invocations}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Active Uptime</div>
        <div class="stat-val">{uptime:.0f}s</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Transport</div>
        <div class="stat-val">HTTP / SSE</div>
      </div>
    </div>

    <div class="card">
      <h2>Connect MCP Client</h2>
      <p style="color: var(--text-muted); font-size: 14px; margin-bottom: 12px;">Add this remote configuration to your Claude Desktop, Cursor, or AI agent environment:</p>
      <pre>{{
  "mcpServers": {{
    "social-analytics": {{
      "url": "{str(request.base_url).rstrip('/')}/mcp"
    }}
  }}
}}</pre>
    </div>

    <div class="card">
      <h2>Live Endpoints</h2>
      <ul class="endpoint-list">
        <li class="endpoint-item">
          <span><strong>MCP Streamable URL:</strong> <code>/mcp</code></span>
          <span style="color: var(--text-muted); font-size: 12px;">Protocol Endpoint</span>
        </li>
        <li class="endpoint-item">
          <span><strong>Real-time Telemetry:</strong> <code>/stats</code></span>
          <a href="/stats" target="_blank">View JSON Stats &rarr;</a>
        </li>
        <li class="endpoint-item">
          <span><strong>Health Status:</strong> <code>/health</code></span>
          <a href="/health" target="_blank">View Health &rarr;</a>
        </li>
      </ul>
    </div>
  </div>
</body>
</html>"""
    return HTMLResponse(content=html)


@mcp.custom_route("/health", methods=["GET"])
async def health_check(request: Request) -> JSONResponse:
    """Simple healthcheck endpoint for Cloud Run and uptime monitors."""
    return JSONResponse({"status": "healthy", "service": "social-analytics-mcp"})


@mcp.custom_route("/stats", methods=["GET"])
async def stats_endpoint(request: Request) -> JSONResponse:
    """Public HTTP telemetry endpoint to inspect user count and tool usage metrics."""
    return JSONResponse(tracker.get_metrics())


@mcp.tool()
async def get_profile_summary(
    username: str, platform: str = "instagram", ctx: Context | None = None
) -> dict:
    """Return public bio and headline counts for an Instagram username or YouTube channel.

    platform: 'instagram' (default) or 'youtube'. For YouTube, username accepts a
    handle such as '@MrBeast', a channel URL, or a UC… channel ID.
    """
    start = time.monotonic()
    client_id = getattr(ctx, "client_id", None) if ctx else None
    result = await asyncio.to_thread(tools.get_profile_summary, username, platform)
    duration_ms = (time.monotonic() - start) * 1000
    tracker.record_call(
        "get_profile_summary",
        {"username": username, "platform": platform},
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
    platform: str = "instagram",
    ctx: Context | None = None,
) -> dict:
    """Return per-item likes, comments, media type, and engagement rates.

    platform: 'instagram' (default) or 'youtube'. YouTube rows also carry view
    counts, and engagement rate is measured against views rather than followers.
    date_range accepts all, a trailing day range such as 30d, or an inclusive
    ISO range such as 2026-01-01:2026-01-31.
    """
    start = time.monotonic()
    client_id = getattr(ctx, "client_id", None) if ctx else None
    result = await asyncio.to_thread(
        tools.get_engagement_metrics, username, date_range, post_limit, platform
    )
    duration_ms = (time.monotonic() - start) * 1000
    tracker.record_call(
        "get_engagement_metrics",
        {"username": username, "date_range": date_range, "post_limit": post_limit, "platform": platform},
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
    output: str = "png",
    platform: str = "instagram",
) -> dict:
    """Generate a light-theme social-performance dashboard for a public account.

    platform: 'instagram' (default) or 'youtube'. metric: follower_growth,
    engagement_rate_over_time, top_posts_by_engagement, content_type_comparison,
    or 'all' for the full audit. chart_type may be line or bar; omitted selects
    the most appropriate chart. The response contains a base64 PNG and an
    interactive Plotly JSON specification.
    """
    start = time.monotonic()
    client_id = getattr(ctx, "client_id", None) if ctx else None
    result = await asyncio.to_thread(
        tools.generate_dashboard, username, metric, chart_type, date_range, top_n, output, platform
    )
    duration_ms = (time.monotonic() - start) * 1000
    tracker.record_call(
        "generate_dashboard",
        {
            "username": username,
            "metric": metric,
            "chart_type": chart_type,
            "date_range": date_range,
            "platform": platform,
        },
        bool(result.get("ok")),
        duration_ms,
        client_id=client_id,
        error_message=result.get("error", {}).get("message"),
    )
    return result


@mcp.tool()
async def audit_profile(
    username: str,
    date_range: str | None = None,
    post_limit: int = 12,
    top_n: int = 5,
    ctx: Context | None = None,
    output: str = "png",
    platform: str = "instagram",
) -> dict:
    """Run a full, single-call performance audit for an Instagram profile or YouTube channel.

    Combines:
    1. Public account stats (authority ratio on Instagram, lifetime views on YouTube).
    2. Ranked top posts/videos bar chart with caption or title snippet labels.
    3. Chronological engagement rate trajectory line chart.
    4. Content-type breakdown (Reels vs Carousels vs Photos, or Shorts vs long-form).
    5. Formatted Markdown tables for items and format distributions.
    6. Actionable AI key takeaways and tactical recommendations.

    platform: 'instagram' (default) or 'youtube'.
    output: 'png' for base64 images, 'spec' for interactive Plotly JSON specs, or 'both'.
    """
    start = time.monotonic()
    client_id = getattr(ctx, "client_id", None) if ctx else None
    result = await asyncio.to_thread(
        tools.audit_profile, username, date_range, post_limit, top_n, output, platform
    )
    duration_ms = (time.monotonic() - start) * 1000
    tracker.record_call(
        "audit_profile",
        {
            "username": username,
            "date_range": date_range,
            "post_limit": post_limit,
            "top_n": top_n,
            "platform": platform,
        },
        bool(result.get("ok")),
        duration_ms,
        client_id=client_id,
        error_message=result.get("error", {}).get("message"),
    )
    return result



@mcp.tool()
def list_available_metrics(platform: str = "instagram", ctx: Context | None = None) -> dict:
    """List supported dashboard metrics, chart types, and data limits for a platform.

    platform: 'instagram' (default) or 'youtube'.
    """
    start = time.monotonic()
    client_id = getattr(ctx, "client_id", None) if ctx else None
    result = tools.list_available_metrics(platform)
    duration_ms = (time.monotonic() - start) * 1000
    tracker.record_call(
        "list_available_metrics",
        {"platform": platform},
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
