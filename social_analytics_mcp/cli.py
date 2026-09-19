"""Terminal harness for making the same calls as the MCP tools."""

from __future__ import annotations

import argparse
import base64
import json
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from .tools import SocialAnalyticsTools


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Test social-analytics-mcp tools from a terminal.")
    commands = parser.add_subparsers(dest="command", required=True)

    profile = commands.add_parser("profile", help="Call get_profile_summary")
    profile.add_argument("username")

    engagement = commands.add_parser("engagement", help="Call get_engagement_metrics")
    engagement.add_argument("username")
    engagement.add_argument("--date-range", default=None)
    engagement.add_argument("--post-limit", type=int, default=12)

    dashboard = commands.add_parser("dashboard", help="Call generate_dashboard")
    dashboard.add_argument("username")
    dashboard.add_argument("metric")
    dashboard.add_argument("--chart-type", choices=("line", "bar"))
    dashboard.add_argument("--date-range", default=None)
    dashboard.add_argument("--top-n", type=int, default=5)
    dashboard.add_argument("--png-output", type=Path, help="Optionally write the returned PNG to this path.")
    dashboard.add_argument(
        "--output",
        choices=("png", "spec", "both"),
        default="png",
        help="Which chart representation(s) to request from the tool.",
    )

    audit = commands.add_parser("audit", help="Call audit_profile (complete account audit with all 3 charts and tables)")
    audit.add_argument("username")
    audit.add_argument("--date-range", default=None)
    audit.add_argument("--post-limit", type=int, default=12)
    audit.add_argument("--top-n", type=int, default=5)
    audit.add_argument(
        "--output",
        choices=("png", "spec", "both"),
        default="png",
        help="Which chart representation(s) to request from the tool.",
    )

    commands.add_parser("metrics", help="Call list_available_metrics")
    return parser


def main() -> None:
    load_dotenv()
    args = build_parser().parse_args()
    toolset = SocialAnalyticsTools()

    if args.command == "profile":
        result = toolset.get_profile_summary(args.username)
    elif args.command == "engagement":
        result = toolset.get_engagement_metrics(args.username, args.date_range, args.post_limit)
    elif args.command == "dashboard":
        result = toolset.generate_dashboard(
            args.username, args.metric, args.chart_type, args.date_range, args.top_n, args.output
        )
        _write_chart_if_requested(result, args.png_output)
        # A base64 PNG makes terminal output unusably long. It is retained in
        # the tool response; CLI output reports its size instead.
        if result.get("ok"):
            image = result.pop("image_png_base64", "")
            result["image_png_base64_length"] = len(image)
    elif args.command == "audit":
        result = toolset.audit_profile(
            args.username, args.date_range, args.post_limit, args.top_n, args.output
        )
        if result.get("ok"):
            for dash_name, dash_data in result.get("dashboards", {}).items():
                if isinstance(dash_data, dict) and "image_png_base64" in dash_data:
                    dash_data["image_png_base64_length"] = len(dash_data.pop("image_png_base64"))
    else:
        result = toolset.list_available_metrics()
    print(json.dumps(result, indent=2, default=str))



def _write_chart_if_requested(result: dict[str, Any], output: Path | None) -> None:
    if not output or not result.get("ok"):
        return
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(base64.b64decode(result["image_png_base64"]))


if __name__ == "__main__":
    main()
