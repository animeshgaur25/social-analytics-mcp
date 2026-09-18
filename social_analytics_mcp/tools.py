"""Framework-independent implementations backing the MCP tools and CLI."""

from __future__ import annotations

import os
from typing import Any

from .apify import ApifyInstagramFetcher
from .cache import FollowerHistory, SessionProfileCache
from .charts import ChartGenerator, DEFAULT_CHART_TYPES, SUPPORTED_CHART_TYPES, SUPPORTED_METRICS
from .errors import SocialAnalyticsError
from .insights import build_content_type_table, build_posts_table, generate_post_insights
from .metrics import average_engagement_rate, normalize_profile, normalize_username, select_posts


class SocialAnalyticsTools:
    """Tool handlers that keep source, transformations, and visualisation separate."""

    def __init__(
        self,
        *,
        fetcher: ApifyInstagramFetcher | None = None,
        cache: SessionProfileCache | None = None,
        follower_history: FollowerHistory | None = None,
        chart_generator: ChartGenerator | None = None,
    ) -> None:
        self._fetcher = fetcher or ApifyInstagramFetcher()
        self._cache = cache or SessionProfileCache(
            ttl_seconds=int(os.getenv("PROFILE_CACHE_TTL_SECONDS", "900"))
        )
        self._follower_history = follower_history or FollowerHistory()
        self._chart_generator = chart_generator or ChartGenerator()

    def get_profile_summary(self, username: str) -> dict[str, Any]:
        try:
            profile, cache_hit = self._profile(username)
            table = (
                f"| Metric | Value |\n|---|---|\n"
                f"| **Username** | @{profile['username']} |\n"
                f"| **Full Name** | {profile['full_name']} |\n"
                f"| **Followers** | {profile['followers']:,} |\n"
                f"| **Following** | {profile['following']:,} |\n"
                f"| **Posts** | {profile['post_count']:,} |\n"
                f"| **Verified** | {'Yes' if profile['verified'] else 'No'} |\n"
                f"| **Bio** | {profile['bio']} |"
            )
            following = profile['following']
            ratio = (profile['followers'] / following) if following else profile['followers']
            insights = [
                f"Follower-to-following ratio is **{ratio:.1f}x**, indicating strong audience authority.",
                f"Account has published **{profile['post_count']:,}** posts on Instagram.",
                f"Verified status: **{'Verified public figure / organization' if profile['verified'] else 'Standard account'}**.",
            ]
            return {
                "ok": True,
                "source": {"provider": "Apify", "actor": "apify/instagram-profile-scraper", "cache_hit": cache_hit},
                "profile": {
                    key: profile[key]
                    for key in ("username", "full_name", "followers", "following", "post_count", "bio", "verified")
                },
                "markdown_table": table,
                "insights": insights,
            }
        except SocialAnalyticsError as exc:
            return self._error(exc)

    def get_engagement_metrics(
        self, username: str, date_range: str | None = None, post_limit: int = 12
    ) -> dict[str, Any]:
        try:
            profile, cache_hit = self._profile(username)
            posts, applied_range = select_posts(profile["posts"], date_range, post_limit)
            if not posts:
                return self._error_message(
                    "No posts matched the requested date range. The Instagram Profile Scraper actor exposes only its latest posts."
                )
            md_table, summary_table = build_posts_table(posts)
            insights = generate_post_insights(profile["username"], posts, profile["followers"])
            return {
                "ok": True,
                "source": {"provider": "Apify", "actor": "apify/instagram-profile-scraper", "cache_hit": cache_hit},
                "username": profile["username"],
                "date_range_applied": applied_range,
                "posts_available_from_actor": len(profile["posts"]),
                "posts_returned": len(posts),
                "average_engagement_rate": average_engagement_rate(posts),
                "average_engagement_rate_percent": round(average_engagement_rate(posts) * 100, 4),
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
    ) -> dict[str, Any]:
        try:
            profile, cache_hit = self._profile(username)
            posts, applied_range = select_posts(profile["posts"], date_range, post_limit=12)
            chart = self._chart_generator.generate(
                username=profile["username"],
                metric=metric,
                posts=posts,
                follower_history=self._follower_history.get(profile["username"]),
                chart_type=chart_type,
                top_n=top_n,
                output=output,
            )

            # Choose appropriate table based on metric
            if metric == "content_type_comparison":
                md_table, summary_table = build_content_type_table(posts)
            elif metric == "top_posts_by_engagement":
                ranked = sorted(posts, key=lambda p: int(p.get("engagement", 0)), reverse=True)
                md_table, summary_table = build_posts_table(ranked, limit=top_n)
            else:
                md_table, summary_table = build_posts_table(posts)

            insights = generate_post_insights(
                profile["username"], posts, profile["followers"], metric=metric
            )

            return {
                "ok": True,
                "source": {"provider": "Apify", "actor": "apify/instagram-profile-scraper", "cache_hit": cache_hit},
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

    @staticmethod
    def list_available_metrics() -> dict[str, Any]:
        return {
            "ok": True,
            "metrics": [
                {
                    "id": "engagement_rate_over_time",
                    "label": "Engagement rate over time",
                    "description": "Likes plus comments divided by the current follower count for each returned post.",
                    "default_chart_type": DEFAULT_CHART_TYPES["engagement_rate_over_time"],
                    "availability": "available from the latest public posts",
                },
                {
                    "id": "top_posts_by_engagement",
                    "label": "Top posts by engagement",
                    "description": "Ranks returned posts by total likes plus comments.",
                    "default_chart_type": DEFAULT_CHART_TYPES["top_posts_by_engagement"],
                    "availability": "available from the latest public posts",
                },
                {
                    "id": "content_type_comparison",
                    "label": "Content-type comparison",
                    "description": "Compares average engagement rate for reels, images, carousels, and videos.",
                    "default_chart_type": DEFAULT_CHART_TYPES["content_type_comparison"],
                    "availability": "available from the latest public posts",
                },
                {
                    "id": "follower_growth",
                    "label": "Follower growth",
                    "description": "Charts follower snapshots collected by this server session.",
                    "default_chart_type": DEFAULT_CHART_TYPES["follower_growth"],
                    "availability": "needs two or more fresh snapshots; the selected Apify actor has no historical follower series",
                },
            ],
            "chart_types": sorted(SUPPORTED_CHART_TYPES),
            "output": {
                "static": "PNG as base64 in image_png_base64",
                "interactive": "A Plotly JSON spec in interactive_chart_spec for clients that support hover, zoom, and pan",
            },
        }

    def _profile(self, username: str) -> tuple[dict[str, Any], bool]:
        normalized_username = normalize_username(username)
        cached = self._cache.get(normalized_username)
        if cached:
            return cached.value, True
        raw = self._fetcher.fetch_profile(normalized_username)
        profile = normalize_profile(raw)
        self._follower_history.record(profile["username"], profile["followers"])
        saved = self._cache.put(normalized_username, profile)
        return saved.value, saved.hit

    @staticmethod
    def _error(exc: SocialAnalyticsError) -> dict[str, Any]:
        return {"ok": False, "error": {"message": str(exc)}}

    @staticmethod
    def _error_message(message: str) -> dict[str, Any]:
        return {"ok": False, "error": {"message": message}}
