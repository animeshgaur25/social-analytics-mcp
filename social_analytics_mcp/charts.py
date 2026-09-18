"""Plotly chart construction, rich interactive styling, and image/HTML export."""

from __future__ import annotations

import base64
import json
import re
from typing import Any

from .errors import ChartRenderingError, InvalidRequestError, NoDataError
from .insights import clean_caption

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

FONT_FAMILY = "Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif"


class ChartGenerator:
    """Produces a static PNG, a Plotly spec, and interactive HTML widgets."""

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
            font={"family": FONT_FAMILY, "color": "#0f172a"},
            margin={"l": 64, "r": 36, "t": 88, "b": 70},
            hovermode="x unified" if resolved_chart_type == "line" else "closest",
            hoverlabel={
                "bgcolor": "#0f172a",
                "font_size": 13,
                "font_family": FONT_FAMILY,
                "font_color": "#ffffff",
                "bordercolor": "#334155",
            },
            width=1100,
            height=620,
        )
        figure.update_xaxes(
            showgrid=False,
            linecolor="#cbd5e1",
            linewidth=1.2,
            tickfont={"size": 11, "family": FONT_FAMILY, "color": "#475569"},
        )
        figure.update_yaxes(
            gridcolor="#f1f5f9",
            gridwidth=1,
            zerolinecolor="#e2e8f0",
            tickfont={"size": 11, "family": FONT_FAMILY, "color": "#475569"},
        )

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
        output: str = "png",   # "png" | "spec" | "both"
    ) -> dict[str, Any]:
        figure, resolved_chart_type = self.build_figure(
            username=username,
            metric=metric,
            posts=posts,
            follower_history=follower_history,
            chart_type=chart_type,
            top_n=top_n,
        )

        result: dict[str, Any] = {
            "metric": metric.strip().lower(),
            "chart_type": resolved_chart_type,
        }

        if output in ("png", "both"):
            try:
                png = figure.to_image(format="png", width=800, height=500, scale=1)
            except Exception as exc:
                raise ChartRenderingError(
                    "The interactive chart was created, but PNG export could not start a compatible browser. "
                    "Install the project's Plotly and Kaleido dependencies and run 'plotly_get_chrome' if needed, then retry."
                ) from exc
            result["image_mime_type"] = "image/png"
            result["image_png_base64"] = base64.b64encode(png).decode("ascii")

        if output in ("spec", "both"):
            result["interactive_chart_spec"] = json.loads(figure.to_json())

        return result
    
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
            trace = go.Bar(
                x=x,
                y=y,
                marker=dict(color="#6366f1", cornerradius=8),
                hovertemplate="<b>%{x}</b><br>Followers: %{y:,}<extra></extra>",
            )
        else:
            trace = go.Scatter(
                x=x,
                y=y,
                mode="lines+markers",
                line=dict(color="#6366f1", width=3),
                marker=dict(size=8, color="#6366f1", line=dict(width=2, color="#ffffff")),
                fill="tozeroy",
                fillcolor="rgba(99, 102, 241, 0.10)",
                hovertemplate="<b>%{x}</b><br>Followers: %{y:,}<extra></extra>",
            )
        figure = go.Figure(trace)
        figure.update_layout(
            title=dict(
                text=f"<b>@{username}</b> · Follower Growth History<br><span style='font-size:12px;color:#64748b;'>Session-tracked follower count checkpoints</span>",
                font=dict(size=18, color="#0f172a"),
            ),
        )
        figure.update_yaxes(title="Followers", tickformat=",")
        return figure

    @staticmethod
    def _engagement_over_time(go: Any, username: str, posts: list[dict[str, Any]], chart_type: str) -> Any:
        ordered = sorted(posts, key=lambda post: post["timestamp"] or "")
        if not ordered:
            raise NoDataError("No dated posts matched this range, so engagement cannot be charted.")
        x = [post["timestamp"][:10] if post.get("timestamp") else "N/A" for post in ordered]
        y = [post["engagement_rate_percent"] for post in ordered]
        avg_rate = sum(y) / len(y)

        hover = [
            f"<b>{clean_caption(post.get('caption'), max_length=40)}</b><br>"
            f"Format: {post['media_type'].title()}<br>"
            f"Likes: {post['likes']:,} · Comments: {post['comments']:,}<br>"
            f"Engagement Rate: <b>{post['engagement_rate_percent']:.2f}%</b>"
            for post in ordered
        ]

        figure = go.Figure()
        if chart_type == "bar":
            figure.add_trace(
                go.Bar(
                    x=x,
                    y=y,
                    marker=dict(color="#0284c7", cornerradius=8),
                    customdata=hover,
                    hovertemplate="%{customdata}<extra></extra>",
                    name="Post Rate",
                )
            )
        else:
            figure.add_trace(
                go.Scatter(
                    x=x,
                    y=y,
                    mode="lines+markers",
                    line=dict(color="#0284c7", width=3),
                    marker=dict(size=9, color="#0284c7", line=dict(width=2, color="#ffffff")),
                    fill="tozeroy",
                    fillcolor="rgba(2, 132, 199, 0.10)",
                    customdata=hover,
                    hovertemplate="%{customdata}<extra></extra>",
                    name="Engagement Rate",
                )
            )

        # Add horizontal benchmark line for average engagement rate
        figure.add_hline(
            y=avg_rate,
            line_dash="dot",
            line_color="#94a3b8",
            line_width=1.5,
            annotation_text=f"Average: {avg_rate:.2f}%",
            annotation_position="top right",
            annotation_font=dict(size=11, color="#64748b"),
        )

        figure.update_layout(
            title=dict(
                text=f"<b>@{username}</b> · Engagement Rate Over Time<br><span style='font-size:12px;color:#64748b;'>Calculated as (likes + comments) / followers per post</span>",
                font=dict(size=18, color="#0f172a"),
            ),
        )
        figure.update_yaxes(title="Engagement rate (%)", ticksuffix="%")
        figure.update_xaxes(title="Publication Date")
        return figure

    @staticmethod
    def _top_posts(go: Any, username: str, posts: list[dict[str, Any]], chart_type: str, top_n: int) -> Any:
        ranked = sorted(posts, key=lambda post: post["engagement"], reverse=True)[:top_n]
        if not ranked:
            raise NoDataError("No posts matched this range, so top posts cannot be charted.")

        # Show short length caption on axis instead of hash id!
        labels = [clean_caption(post.get("caption"), max_length=24) for post in ranked]
        values = [post["engagement"] for post in ranked]
        hover = [
            f"<b>{clean_caption(post.get('caption'), max_length=50)}</b><br>"
            f"Format: {post['media_type'].title()}<br>"
            f"Likes: {post['likes']:,} · Comments: {post['comments']:,}<br>"
            f"Total Engagement: <b>{post['engagement']:,}</b><br>"
            f"Engagement Rate: <b>{post['engagement_rate_percent']:.2f}%</b>"
            for post in ranked
        ]

        if chart_type == "line":
            trace = go.Scatter(
                x=labels,
                y=values,
                mode="lines+markers",
                line=dict(color="#f97316", width=3.5),
                marker=dict(size=9, color="#f97316", line=dict(width=2, color="#ffffff")),
                customdata=hover,
                hovertemplate="%{customdata}<extra></extra>",
            )
        else:
            # Modern bar with cornerradius and data labels
            trace = go.Bar(
                x=labels,
                y=values,
                marker=dict(color="#f97316", cornerradius=8),
                text=[f"{v:,}" for v in values],
                textposition="outside",
                textfont=dict(size=11, color="#475569", family=FONT_FAMILY),
                customdata=hover,
                hovertemplate="%{customdata}<extra></extra>",
            )

        figure = go.Figure(trace)
        figure.update_layout(
            title=dict(
                text=f"<b>@{username}</b> · Top {len(ranked)} Posts by Engagement<br><span style='font-size:12px;color:#64748b;'>Ranked by total likes + comments (labeled by caption snippet)</span>",
                font=dict(size=18, color="#0f172a"),
            ),
        )
        figure.update_yaxes(title="Likes + comments", tickformat=",")
        figure.update_xaxes(title="Post (Caption snippet)")
        return figure

    @staticmethod
    def _content_types(go: Any, username: str, posts: list[dict[str, Any]], chart_type: str) -> Any:
        groups: dict[str, list[float]] = {}
        counts: dict[str, int] = {}
        for post in posts:
            m_type = post["media_type"].title()
            groups.setdefault(m_type, []).append(post["engagement_rate_percent"])
            counts[m_type] = counts.get(m_type, 0) + 1

        if not groups:
            raise NoDataError("No posts matched this range, so content types cannot be compared.")

        labels = sorted(groups)
        values = [sum(groups[label]) / len(groups[label]) for label in labels]
        hover = [
            f"<b>{label}</b><br>"
            f"Posts Analyzed: {counts[label]}<br>"
            f"Average Engagement Rate: <b>{val:.2f}%</b>"
            for label, val in zip(labels, values)
        ]

        if chart_type == "line":
            trace = go.Scatter(
                x=labels,
                y=values,
                mode="lines+markers",
                line=dict(color="#10b981", width=3.5),
                marker=dict(size=9, color="#10b981", line=dict(width=2, color="#ffffff")),
                customdata=hover,
                hovertemplate="%{customdata}<extra></extra>",
            )
        else:
            trace = go.Bar(
                x=labels,
                y=values,
                marker=dict(color="#10b981", cornerradius=8),
                text=[f"{v:.2f}%" for v in values],
                textposition="outside",
                textfont=dict(size=11, color="#475569", family=FONT_FAMILY),
                customdata=hover,
                hovertemplate="%{customdata}<extra></extra>",
            )

        figure = go.Figure(trace)
        figure.update_layout(
            title=dict(
                text=f"<b>@{username}</b> · Average Engagement by Content Type<br><span style='font-size:12px;color:#64748b;'>Comparison of Reels, Carousels, Static Images, and Videos</span>",
                font=dict(size=18, color="#0f172a"),
            ),
        )
        figure.update_yaxes(title="Average engagement rate (%)", ticksuffix="%")
        figure.update_xaxes(title="Content Format")
        return figure

