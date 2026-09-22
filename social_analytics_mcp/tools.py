"""Framework-independent implementations backing the MCP tools and CLI."""

from __future__ import annotations

import os
from typing import Any

from .apify import ApifyInstagramFetcher, ApifyYouTubeFetcher
from .cache import FollowerHistory, SessionProfileCache
from .charts import ChartGenerator, DEFAULT_CHART_TYPES, SUPPORTED_CHART_TYPES, SUPPORTED_METRICS
from .errors import SocialAnalyticsError
from .insights import build_content_type_table, build_posts_table, generate_post_insights
from .metrics import (
    average_engagement_rate,
    normalize_channel_handle,
    normalize_profile,
    normalize_username,
    normalize_youtube_channel,
    select_posts,
    youtube_channel_url,
)
from .platforms import PlatformSpec, SUPPORTED_PLATFORMS, resolve_platform


class SocialAnalyticsTools:
    """Tool handlers that keep source, transformations, and visualisation separate."""

    def __init__(
        self,
        *,
        fetcher: ApifyInstagramFetcher | None = None,
        youtube_fetcher: ApifyYouTubeFetcher | None = None,
        cache: SessionProfileCache | None = None,
        follower_history: FollowerHistory | None = None,
        chart_generator: ChartGenerator | None = None,
    ) -> None:
        self._fetcher = fetcher or ApifyInstagramFetcher()
        self._youtube_fetcher = youtube_fetcher or ApifyYouTubeFetcher()
        self._cache = cache or SessionProfileCache(
            ttl_seconds=int(os.getenv("PROFILE_CACHE_TTL_SECONDS", "900"))
        )
        self._follower_history = follower_history or FollowerHistory()
        self._chart_generator = chart_generator or ChartGenerator()

    def get_profile_summary(self, username: str, platform: str = "instagram") -> dict[str, Any]:
        try:
            spec = resolve_platform(platform)
            profile, cache_hit, actor_id = self._profile(username, spec)
            rows = [
                ("Username", f"@{profile['username']}"),
                ("Full Name", profile["full_name"]),
                (spec.audience_noun, f"{profile['followers']:,}"),
            ]
            if spec.tracks_following:
                rows.append(("Following", f"{profile['following']:,}"))
            if profile.get("channel_total_views"):
                rows.append(("Total Channel Views", f"{profile['channel_total_views']:,}"))
            rows.extend(
                [
                    (spec.item_noun_plural.title(), f"{profile['post_count']:,}"),
                    ("Verified", "Yes" if profile["verified"] else "No"),
                    ("Bio", profile["bio"]),
                ]
            )
            table = "| Metric | Value |\n|---|---|\n" + "\n".join(
                f"| **{label}** | {value} |" for label, value in rows
            )

            insights = [
                f"Account has published **{profile['post_count']:,}** {spec.item_noun_plural} on {spec.label}.",
                f"Verified status: **{'Verified public figure / organization' if profile['verified'] else 'Standard account'}**.",
            ]
            if spec.tracks_following:
                following = profile["following"]
                ratio = (profile["followers"] / following) if following else profile["followers"]
                insights.insert(
                    0,
                    f"Follower-to-following ratio is **{ratio:.1f}x**, indicating strong audience authority.",
                )
            elif profile.get("channel_total_views") and profile["post_count"]:
                per_video = profile["channel_total_views"] / profile["post_count"]
                insights.insert(
                    0,
                    f"Lifetime library averages **{per_video:,.0f}** views per video across "
                    f"{profile['channel_total_views']:,} total channel views.",
                )

            summary = {
                key: profile[key]
                for key in ("username", "full_name", "followers", "following", "post_count", "bio", "verified")
            }
            if spec.id == "youtube":
                summary["subscribers"] = profile["followers"]
                summary["channel_url"] = profile.get("channel_url", "")
                summary["channel_total_views"] = profile.get("channel_total_views", 0)

            return {
                "ok": True,
                "source": self._source(spec, actor_id, cache_hit),
                "platform": spec.id,
                "profile": summary,
                "markdown_table": table,
                "insights": insights,
            }
        except SocialAnalyticsError as exc:
            return self._error(exc)

    def get_engagement_metrics(
        self,
        username: str,
        date_range: str | None = None,
        post_limit: int = 12,
        platform: str = "instagram",
    ) -> dict[str, Any]:
        try:
            spec = resolve_platform(platform)
            profile, cache_hit, actor_id = self._profile(username, spec)
            posts, applied_range = select_posts(profile["posts"], date_range, post_limit)
            if not posts:
                return self._error_message(
                    f"No {spec.item_noun_plural} matched the requested date range. "
                    f"The {actor_id} actor exposes only its most recent {spec.item_noun_plural}."
                )
            md_table, summary_table = build_posts_table(posts, platform=spec.id)
            insights = generate_post_insights(
                profile["username"], posts, profile["followers"], platform=spec.id
            )
            return {
                "ok": True,
                "source": self._source(spec, actor_id, cache_hit),
                "platform": spec.id,
                "username": profile["username"],
                "date_range_applied": applied_range,
                "posts_available_from_actor": len(profile["posts"]),
                "posts_returned": len(posts),
                "average_engagement_rate": average_engagement_rate(posts),
                "average_engagement_rate_percent": round(average_engagement_rate(posts) * 100, 4),
                "engagement_rate_basis": spec.engagement_basis,
                "markdown_table": md_table,
                "summary_table": summary_table,
                "insights": insights["key_takeaways"],
                "recommendations": insights["recommendations"],
                "posts": posts,
            }
        except SocialAnalyticsError as exc:
            return self._error(exc)

    def generate_dashboard(
        self,
        username: str,
        metric: str,
        chart_type: str | None = None,
        date_range: str | None = None,
        top_n: int = 5,
        output: str = "png",
        platform: str = "instagram",
    ) -> dict[str, Any]:
        if metric.strip().lower() == "all":
            return self.audit_profile(
                username=username,
                date_range=date_range,
                post_limit=12,
                top_n=top_n,
                output=output,
                platform=platform,
            )

        try:
            spec = resolve_platform(platform)
            profile, cache_hit, actor_id = self._profile(username, spec)
            posts, applied_range = select_posts(profile["posts"], date_range, post_limit=12)
            chart = self._chart_generator.generate(
                username=profile["username"],
                metric=metric,
                posts=posts,
                follower_history=self._follower_history.get(self._history_key(spec, profile)),
                chart_type=chart_type,
                top_n=top_n,
                output=output,
                platform=spec.id,
            )

            # Choose appropriate table based on metric
            if metric == "content_type_comparison":
                md_table, summary_table = build_content_type_table(posts, platform=spec.id)
            elif metric == "top_posts_by_engagement":
                ranked = sorted(posts, key=lambda p: int(p.get("engagement", 0)), reverse=True)
                md_table, summary_table = build_posts_table(ranked, limit=top_n, platform=spec.id)
            else:
                md_table, summary_table = build_posts_table(posts, platform=spec.id)

            insights = generate_post_insights(
                profile["username"], posts, profile["followers"], metric=metric, platform=spec.id
            )

            return {
                "ok": True,
                "source": self._source(spec, actor_id, cache_hit),
                "platform": spec.id,
                "username": profile["username"],
                "date_range_applied": applied_range,
                "posts_used": len(posts),
                "markdown_table": md_table,
                "summary_table": summary_table,
                "insights": insights["key_takeaways"],
                "recommendations": insights["recommendations"],
                **chart,
            }
        except SocialAnalyticsError as exc:
            return self._error(exc)

    def audit_profile(
        self,
        username: str,
        date_range: str | None = None,
        post_limit: int = 12,
        top_n: int = 5,
        output: str = "png",
        platform: str = "instagram",
    ) -> dict[str, Any]:
        """Perform a comprehensive account audit returning all 3 dashboard views, tables, and insights in one call."""
        try:
            spec = resolve_platform(platform)
            profile, cache_hit, actor_id = self._profile(username, spec)
            posts, applied_range = select_posts(profile["posts"], date_range, post_limit=post_limit)
            history = self._follower_history.get(self._history_key(spec, profile))

            # 1. Top Posts by Engagement
            ranked_posts = sorted(posts, key=lambda p: int(p.get("engagement", 0)), reverse=True)
            top_posts_chart = self._chart_generator.generate(
                username=profile["username"],
                metric="top_posts_by_engagement",
                posts=posts,
                follower_history=history,
                chart_type="bar",
                top_n=top_n,
                output=output,
                platform=spec.id,
            )
            top_posts_table_md, _ = build_posts_table(ranked_posts, limit=top_n, platform=spec.id)

            # 2. Engagement Rate Over Time
            trajectory_chart = self._chart_generator.generate(
                username=profile["username"],
                metric="engagement_rate_over_time",
                posts=posts,
                follower_history=history,
                chart_type="line",
                top_n=top_n,
                output=output,
                platform=spec.id,
            )

            # 3. Content Type Comparison
            content_type_chart = self._chart_generator.generate(
                username=profile["username"],
                metric="content_type_comparison",
                posts=posts,
                follower_history=history,
                chart_type="bar",
                top_n=top_n,
                output=output,
                platform=spec.id,
            )
            content_type_table_md, _ = build_content_type_table(posts, platform=spec.id)

            # Comprehensive Insights & Recommendations
            insights = generate_post_insights(
                profile["username"], posts, profile["followers"], platform=spec.id
            )

            profile_block = {
                "username": profile["username"],
                "full_name": profile["full_name"],
                "followers": profile["followers"],
                "following": profile["following"],
                "post_count": profile["post_count"],
                "verified": profile["verified"],
                "bio": profile["bio"],
            }
            if spec.tracks_following:
                following = profile.get("following") or 0
                ratio = (profile["followers"] / following) if following else profile["followers"]
                profile_block["authority_ratio"] = f"{ratio:.1f}x"
                headline = (
                    f"**Followers:** {profile['followers']:,} | **Following:** {profile['following']:,} "
                    f"({ratio:.1f}x authority ratio) | **Posts:** {profile['post_count']:,} | "
                    f"**Verified:** {'Yes' if profile['verified'] else 'No'}"
                )
            else:
                profile_block["channel_url"] = profile.get("channel_url", "")
                profile_block["channel_total_views"] = profile.get("channel_total_views", 0)
                headline = (
                    f"**Subscribers:** {profile['followers']:,} | "
                    f"**Lifetime views:** {profile.get('channel_total_views', 0):,} | "
                    f"**Videos:** {profile['post_count']:,} | "
                    f"**Verified:** {'Yes' if profile['verified'] else 'No'}"
                )

            report_lines = [
                f"# Performance Audit: @{profile['username']} ({profile['full_name']}) · {spec.label}",
                headline,
                "",
                f"## 1. Top {spec.item_noun_plural.title()} by Engagement",
                top_posts_table_md,
                "",
                "## 2. Content-Type Breakdown",
                content_type_table_md,
                "",
                "## 3. Key Takeaways",
                *[f"- {t}" for t in insights["key_takeaways"]],
                "",
                "## 4. Strategic Recommendations",
                *[f"- {r}" for r in insights["recommendations"]],
            ]
            audit_markdown_report = "\n".join(report_lines)

            return {
                "ok": True,
                "source": self._source(spec, actor_id, cache_hit),
                "platform": spec.id,
                "username": profile["username"],
                "profile": profile_block,
                "date_range_applied": applied_range,
                "posts_analyzed": len(posts),
                "dashboards": {
                    "top_posts_by_engagement": top_posts_chart,
                    "engagement_rate_over_time": trajectory_chart,
                    "content_type_comparison": content_type_chart,
                },
                "tables": {
                    "top_posts_markdown": top_posts_table_md,
                    "content_type_markdown": content_type_table_md,
                },
                "audit_markdown_report": audit_markdown_report,
                "insights": insights["key_takeaways"],
                "recommendations": insights["recommendations"],
                "benchmark": insights["benchmark"],
            }
        except SocialAnalyticsError as exc:
            return self._error(exc)

    @staticmethod
    def list_available_metrics(platform: str = "instagram") -> dict[str, Any]:
        try:
            spec = resolve_platform(platform)
        except SocialAnalyticsError as exc:
            return SocialAnalyticsTools._error(exc)

        item = spec.item_noun
        items = spec.item_noun_plural
        audience = spec.audience_noun
        availability = f"available from the latest public {items}"
        formats = (
            "Shorts, long-form videos, and livestreams"
            if spec.id == "youtube"
            else "reels, images, carousels, and videos"
        )
        return {
            "ok": True,
            "platform": spec.id,
            "platforms_supported": sorted(SUPPORTED_PLATFORMS),
            "metrics": [
                {
                    "id": "engagement_rate_over_time",
                    "label": "Engagement rate over time",
                    "description": f"Likes plus comments divided by {spec.engagement_basis} for each returned {item}.",
                    "default_chart_type": DEFAULT_CHART_TYPES["engagement_rate_over_time"],
                    "availability": availability,
                },
                {
                    "id": "top_posts_by_engagement",
                    "label": f"Top {items} by engagement",
                    "description": f"Ranks returned {items} by total likes plus comments.",
                    "default_chart_type": DEFAULT_CHART_TYPES["top_posts_by_engagement"],
                    "availability": availability,
                },
                {
                    "id": "content_type_comparison",
                    "label": "Content-type comparison",
                    "description": f"Compares average engagement rate for {formats}.",
                    "default_chart_type": DEFAULT_CHART_TYPES["content_type_comparison"],
                    "availability": availability,
                },
                {
                    "id": "follower_growth",
                    "label": f"{audience} growth",
                    "description": f"Charts {audience.lower()} snapshots collected by this server session.",
                    "default_chart_type": DEFAULT_CHART_TYPES["follower_growth"],
                    "availability": (
                        "needs two or more fresh snapshots; the selected Apify actor has no "
                        f"historical {audience.lower()} series"
                    ),
                },
            ],
            "chart_types": sorted(SUPPORTED_CHART_TYPES),
            "output": {
                "static": "PNG as base64 in image_png_base64",
                "interactive": "A Plotly JSON spec in interactive_chart_spec for clients that support hover, zoom, and pan",
            },
        }

    def _profile(self, username: str, spec: PlatformSpec) -> tuple[dict[str, Any], bool, str]:
        if spec.id == "youtube":
            reference = normalize_channel_handle(username)
            actor_id = self._youtube_fetcher.actor_id
        else:
            reference = normalize_username(username)
            actor_id = self._fetcher.actor_id

        cache_key = f"{spec.id}:{reference}"
        cached = self._cache.get(cache_key)
        if cached:
            return cached.value, True, actor_id

        if spec.id == "youtube":
            items = self._youtube_fetcher.fetch_channel(youtube_channel_url(reference))
            profile = normalize_youtube_channel(items, reference)
        else:
            profile = normalize_profile(self._fetcher.fetch_profile(reference))

        self._follower_history.record(self._history_key(spec, profile), profile["followers"])
        saved = self._cache.put(cache_key, profile)
        return saved.value, saved.hit, actor_id

    @staticmethod
    def _history_key(spec: PlatformSpec, profile: dict[str, Any]) -> str:
        return f"{spec.id}:{profile['username']}"

    @staticmethod
    def _source(spec: PlatformSpec, actor_id: str, cache_hit: bool) -> dict[str, Any]:
        return {
            "provider": "Apify",
            "platform": spec.id,
            "actor": actor_id,
            "cache_hit": cache_hit,
        }

    @staticmethod
    def _error(exc: SocialAnalyticsError) -> dict[str, Any]:
        return {"ok": False, "error": {"message": str(exc)}}

    @staticmethod
    def _error_message(message: str) -> dict[str, Any]:
        return {"ok": False, "error": {"message": message}}
