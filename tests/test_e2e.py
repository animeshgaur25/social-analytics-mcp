"""Deliberately opt-in live smoke test for every public MCP tool.

Run this only with an Apify token. It incurs the actor's normal usage cost.
"""

from __future__ import annotations

import asyncio
import base64
import json
import os
from pathlib import Path
import sys

from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

USERNAME = "eminem"
CHART_REQUESTS = (
    ("engagement_rate_over_time", "line"),
    ("top_posts_by_engagement", "bar"),
    ("content_type_comparison", "bar"),
)


def require_ok(name: str, response: dict) -> dict:
    if not response.get("ok"):
        raise RuntimeError(f"{name} failed: {response.get('error', {}).get('message', 'unknown error')}")
    print(f"✓ {name}")
    return response


def as_dict(result: object) -> dict:
    """Support current MCP structured results and plain JSON-text fallback."""
    structured = getattr(result, "structuredContent", None)
    if isinstance(structured, dict):
        return structured
    for content in getattr(result, "content", []):
        if getattr(content, "type", None) == "text":
            return json.loads(content.text)
    raise RuntimeError("The MCP tool did not return a JSON object.")


async def run_live_smoke_test() -> None:
    project_root = Path(__file__).parents[1]
    parameters = StdioServerParameters(
        command=sys.executable,
        args=["-m", "social_analytics_mcp"],
        env=os.environ.copy(),
        cwd=str(project_root),
    )
    async with stdio_client(parameters) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            require_ok("list_available_metrics", as_dict(await session.call_tool("list_available_metrics")))
            require_ok(
                "get_profile_summary",
                as_dict(await session.call_tool("get_profile_summary", {"username": USERNAME})),
            )
            require_ok(
                "get_engagement_metrics",
                as_dict(
                    await session.call_tool(
                        "get_engagement_metrics",
                        {"username": USERNAME, "date_range": "all", "post_limit": 12},
                    )
                ),
            )
            for metric, chart_type in CHART_REQUESTS:
                dashboard = require_ok(
                    f"generate_dashboard ({metric})",
                    as_dict(
                        await session.call_tool(
                            "generate_dashboard",
                            {
                                "username": USERNAME,
                                "metric": metric,
                                "chart_type": chart_type,
                                "date_range": "all",
                            },
                        )
                    ),
                )
                png_path = Path(f"eminem_{metric}.png")
                spec_path = Path(f"eminem_{metric}.plotly.json")
                png_path.write_bytes(base64.b64decode(dashboard["image_png_base64"]))
                spec_path.write_text(json.dumps(dashboard["interactive_chart_spec"], indent=2))
                print(f"✓ Wrote {png_path.resolve()} and {spec_path.resolve()}")


def main() -> None:
    load_dotenv()
    if not os.getenv("APIFY_API_TOKEN"):
        raise SystemExit("APIFY_API_TOKEN is required. Copy .env.example to .env and set the token first.")

    asyncio.run(run_live_smoke_test())


if __name__ == "__main__":
    main()
