"""Plotly chart construction and PNG/base64 encoding."""

from __future__ import annotations

import base64
import json
from typing import Any

from .errors import ChartRenderingError, InvalidRequestError, NoDataError

SUPPORTED_METRICS = {
    "follower_growth",
    "engagement_rate_over_time",
    "top_posts_by_engagement",
    "content_type_comparison",
}
SUPPORTED_CHART_TYPES = {"line", "bar"}

DEFAULT_CHART_TYPES = {
    "follower_growth": "line",
    "engagement_rate_over_time": "line",
    "top_posts_by_engagement": "bar",
    "content_type_comparison": "bar",
}


class ChartGenerator:
    """Produces a static PNG plus a portable Plotly spec for interactive clients."""

    def build_figure(
        self,
        *,
        username: str,
        metric: str,
        posts: list[dict[str, Any]],
        follower_history: list[dict[str, Any]],
        chart_type: str | None,
        top_n: int,
    ) -> tuple[Any, str]:
        """Create the interactive Plotly figure without exporting an image.

        Keeping figure construction separate makes chart semantics directly
        testable without a running browser/Kaleido installation.
        """
        metric = metric.strip().lower()
        if metric not in SUPPORTED_METRICS:
            raise InvalidRequestError(
                f"Unsupported metric '{metric}'. Use one of: {', '.join(sorted(SUPPORTED_METRICS))}."
            )
        resolved_chart_type = (chart_type or DEFAULT_CHART_TYPES[metric]).lower()
        if resolved_chart_type not in SUPPORTED_CHART_TYPES:
            raise InvalidRequestError("chart_type must be 'line' or 'bar'.")
        if top_n < 1:
            raise InvalidRequestError("top_n must be at least 1.")

        go = self._plotly()
        if metric == "follower_growth":
            figure = self._follower_growth(go, username, follower_history, resolved_chart_type)
        elif metric == "engagement_rate_over_time":
            figure = self._engagement_over_time(go, username, posts, resolved_chart_type)
        elif metric == "top_posts_by_engagement":
            figure = self._top_posts(go, username, posts, resolved_chart_type, top_n)
        else:
            figure = self._content_types(go, username, posts, resolved_chart_type)

        figure.update_layout(
            template="plotly_white",
            paper_bgcolor="#ffffff",
            plot_bgcolor="#ffffff",
            font={"family": "Inter, Arial, sans-serif", "color": "#1f2937"},
            margin={"l": 60, "r": 30, "t": 72, "b": 60},
            hovermode="x unified" if resolved_chart_type == "line" else "closest",
            width=1100,
            height=620,
        )
        figure.update_xaxes(showgrid=False, linecolor="#d1d5db")
        figure.update_yaxes(gridcolor="#e5e7eb", zerolinecolor="#e5e7eb")

        return figure, resolved_chart_type

    def generate(
        self,
        *,
        username: str,
        metric: str,
        posts: list[dict[str, Any]],
        follower_history: list[dict[str, Any]],
        chart_type: str | None,
        top_n: int,
    ) -> dict[str, Any]:
        """Create a Plotly figure, its PNG representation, and its JSON spec."""
        figure, resolved_chart_type = self.build_figure(
            username=username,
            metric=metric,
            posts=posts,
            follower_history=follower_history,
            chart_type=chart_type,
            top_n=top_n,
        )
        try:
            png = figure.to_image(format="png", width=1100, height=620, scale=2)
        except Exception as exc:
            raise ChartRenderingError(
                "The interactive chart was created, but PNG export could not start a compatible browser. "
                "Install the project's Plotly and Kaleido dependencies and run 'plotly_get_chrome' if needed, then retry."
            ) from exc

        # JSON is deliberately included alongside the PNG. MCP clients that can
        # render Plotly may use it to retain hover/zoom/pan interactions.
        return {
            "metric": metric.strip().lower(),
            "chart_type": resolved_chart_type,
            "image_mime_type": "image/png",
            "image_png_base64": base64.b64encode(png).decode("ascii"),
            "interactive_chart_spec": json.loads(figure.to_json()),
        }

    @staticmethod
    def _plotly() -> Any:
        try:
            import plotly.graph_objects as go
        except ImportError as exc:
            raise ChartRenderingError(
                "Plotly is not installed. Install the project dependencies and restart the server."
            ) from exc
        return go

    @staticmethod
    def _follower_growth(go: Any, username: str, history: list[dict[str, Any]], chart_type: str) -> Any:
        if len(history) < 2:
            raise NoDataError(
                "Follower growth needs at least two fresh profile snapshots. "
                "This Apify actor supplies the current follower count only; run the profile tool again "
                "after time has passed, or connect a historical source."
            )
        x = [entry["timestamp"] for entry in history]
        y = [entry["followers"] for entry in history]
        if chart_type == "bar":
            figure = go.Figure(go.Bar(x=x, y=y, marker_color="#4f46e5"))
        else:
            figure = go.Figure(
                go.Scatter(x=x, y=y, mode="lines+markers", line={"color": "#4f46e5", "width": 3})
            )
        figure.update_layout(title=f"@{username} follower snapshots")
        figure.update_yaxes(title="Followers", tickformat=",")
        return figure

    @staticmethod
    def _engagement_over_time(go: Any, username: str, posts: list[dict[str, Any]], chart_type: str) -> Any:
        ordered = sorted(posts, key=lambda post: post["timestamp"] or "")
        if not ordered:
            raise NoDataError("No dated posts matched this range, so engagement cannot be charted.")
        x = [post["timestamp"] for post in ordered]
        y = [post["engagement_rate_percent"] for post in ordered]
        hover = [
            f"{post['media_type'].title()}<br>{post['likes']:,} likes · {post['comments']:,} comments"
            for post in ordered
        ]
        if chart_type == "bar":
            trace = go.Bar(x=x, y=y, marker_color="#0ea5e9", customdata=hover, hovertemplate="%{customdata}<br>%{y:.3f}%<extra></extra>")
        else:
            trace = go.Scatter(
                x=x,
                y=y,
                mode="lines+markers",
                line={"color": "#0ea5e9", "width": 3},
                customdata=hover,
                hovertemplate="%{customdata}<br>%{y:.3f}%<extra></extra>",
            )
        figure = go.Figure(trace)
        figure.update_layout(title=f"@{username} engagement rate over time")
        figure.update_yaxes(title="Engagement rate (%)", ticksuffix="%")
        return figure

    @staticmethod
    def _top_posts(go: Any, username: str, posts: list[dict[str, Any]], chart_type: str, top_n: int) -> Any:
        ranked = sorted(posts, key=lambda post: post["engagement"], reverse=True)[:top_n]
        if not ranked:
            raise NoDataError("No posts matched this range, so top posts cannot be charted.")
        labels = [post["shortcode"] or (post["timestamp"] or "Unknown date")[:10] for post in ranked]
        values = [post["engagement"] for post in ranked]
        hover = [
            f"{post['media_type'].title()}<br>{post['likes']:,} likes · {post['comments']:,} comments<br>{post['engagement_rate_percent']:.3f}% rate"
            for post in ranked
        ]
        if chart_type == "line":
            trace = go.Scatter(x=labels, y=values, mode="lines+markers", line={"color": "#f97316", "width": 3})
        else:
            trace = go.Bar(x=labels, y=values, marker_color="#f97316")
        trace.update(customdata=hover, hovertemplate="%{customdata}<br>%{y:,} total engagements<extra></extra>")
        figure = go.Figure(trace)
        figure.update_layout(title=f"@{username} top {len(ranked)} posts by engagement")
        figure.update_yaxes(title="Likes + comments", tickformat=",")
        figure.update_xaxes(title="Post")
        return figure

    @staticmethod
    def _content_types(go: Any, username: str, posts: list[dict[str, Any]], chart_type: str) -> Any:
        groups: dict[str, list[float]] = {}
        for post in posts:
            groups.setdefault(post["media_type"], []).append(post["engagement_rate_percent"])
        if not groups:
            raise NoDataError("No posts matched this range, so content types cannot be compared.")
        labels = sorted(groups)
        values = [sum(groups[label]) / len(groups[label]) for label in labels]
        counts = [len(groups[label]) for label in labels]
        hover = [f"{count} post{'s' if count != 1 else ''}" for count in counts]
        if chart_type == "line":
            trace = go.Scatter(x=labels, y=values, mode="lines+markers", line={"color": "#10b981", "width": 3})
        else:
            trace = go.Bar(x=labels, y=values, marker_color="#10b981")
        trace.update(customdata=hover, hovertemplate="%{x}: %{y:.3f}%<br>%{customdata}<extra></extra>")
        figure = go.Figure(trace)
        figure.update_layout(title=f"@{username} average engagement by content type")
        figure.update_yaxes(title="Average engagement rate (%)", ticksuffix="%")
        figure.update_xaxes(title="Content type")
        return figure
