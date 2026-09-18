"""Analytics tables and actionable insights generation for social performance."""

from __future__ import annotations

import re
from typing import Any


def clean_caption(caption: str | None, max_length: int = 35) -> str:
    """Format and truncate post captions cleanly for labels and tables."""
    if not caption:
        return "Untitled Post"
    # Remove emojis/newlines/hashtags cleanup for compact display
    cleaned = re.sub(r"\s+", " ", caption).strip()
    # Strip leading hashtags or @mentions if they dominate
    if len(cleaned) > max_length:
        return cleaned[: max_length - 3].rstrip() + "..."
    return cleaned or "Untitled Post"


def build_posts_table(posts: list[dict[str, Any]], limit: int | None = None) -> tuple[str, list[dict[str, Any]]]:
    """Generate both a Markdown table string and structured row dicts for posts."""
    subset = posts[:limit] if limit else posts
    rows: list[dict[str, Any]] = []

    for idx, post in enumerate(subset, start=1):
        caption_short = clean_caption(post.get("caption"), max_length=40)
        date_str = str(post.get("timestamp") or "")[:10] or "N/A"
        media = str(post.get("media_type") or "image").title()
        likes = int(post.get("likes") or 0)
        comments = int(post.get("comments") or 0)
        total_eng = int(post.get("engagement") or (likes + comments))
        rate_pct = float(post.get("engagement_rate_percent") or 0.0)

        rows.append({
            "rank": idx,
            "caption": caption_short,
            "full_caption": post.get("caption") or "",
            "media_type": media,
            "likes": likes,
            "comments": comments,
            "total_engagement": total_eng,
            "engagement_rate_percent": rate_pct,
            "date": date_str,
            "url": post.get("url") or "",
            "shortcode": post.get("shortcode") or "",
        })

    # Build Markdown table
    md_lines = [
        "| # | Post Caption | Type | Likes | Comments | Total Eng. | Eng. Rate | Date |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        md_lines.append(
            f"| {r['rank']} | {r['caption']} | {r['media_type']} | {r['likes']:,} | {r['comments']:,} | {r['total_engagement']:,} | {r['engagement_rate_percent']:.2f}% | {r['date']} |"
        )
    markdown_table = "\n".join(md_lines)

    return markdown_table, rows


def build_content_type_table(posts: list[dict[str, Any]]) -> tuple[str, list[dict[str, Any]]]:
    """Summarize performance by content type (reel, carousel, image, video)."""
    groups: dict[str, list[dict[str, Any]]] = {}
    for post in posts:
        groups.setdefault(post.get("media_type", "image"), []).append(post)

    rows: list[dict[str, Any]] = []
    total_posts = len(posts) or 1

    for media_type, items in sorted(groups.items(), key=lambda x: len(x[1]), reverse=True):
        count = len(items)
        avg_likes = sum(int(p.get("likes", 0)) for p in items) / count
        avg_comments = sum(int(p.get("comments", 0)) for p in items) / count
        avg_rate = sum(float(p.get("engagement_rate_percent", 0.0)) for p in items) / count
        share = (count / total_posts) * 100

        rows.append({
            "content_type": media_type.title(),
            "posts_count": count,
            "share_of_posts_percent": round(share, 1),
            "average_likes": round(avg_likes, 1),
            "average_comments": round(avg_comments, 1),
            "average_engagement_rate_percent": round(avg_rate, 3),
        })

    md_lines = [
        "| Content Type | Posts | Share | Avg Likes | Avg Comments | Avg Eng. Rate |",
        "|---|---|---|---|---|---|",
    ]
    for r in rows:
        md_lines.append(
            f"| {r['content_type']} | {r['posts_count']} | {r['share_of_posts_percent']}% | {r['average_likes']:,.0f} | {r['average_comments']:,.0f} | {r['average_engagement_rate_percent']:.2f}% |"
        )
    markdown_table = "\n".join(md_lines)

    return markdown_table, rows


def generate_post_insights(
    username: str,
    posts: list[dict[str, Any]],
    followers: int,
    metric: str | None = None,
) -> dict[str, Any]:
    """Generate high-value analytical takeaways and recommendations from posts."""
    if not posts:
        return {
            "key_takeaways": ["No post data available for the selected timeframe."],
            "recommendations": ["Expand the date range to capture recent posts."],
        }

    total_likes = sum(int(p.get("likes", 0)) for p in posts)
    total_comments = sum(int(p.get("comments", 0)) for p in posts)
    avg_rate = sum(float(p.get("engagement_rate_percent", 0.0)) for p in posts) / len(posts)

    # Top post by engagement
    sorted_by_eng = sorted(posts, key=lambda p: int(p.get("engagement", 0)), reverse=True)
    top_post = sorted_by_eng[0]
    top_caption = clean_caption(top_post.get("caption"), max_length=45)
    top_eng = int(top_post.get("engagement", 0))
    top_rate = float(top_post.get("engagement_rate_percent", 0.0))

    # Content type breakdown
    type_groups: dict[str, list[float]] = {}
    for p in posts:
        type_groups.setdefault(p.get("media_type", "image"), []).append(float(p.get("engagement_rate_percent", 0.0)))

    best_type = max(type_groups.items(), key=lambda x: sum(x[1]) / len(x[1])) if type_groups else ("image", [0])
    best_type_name = best_type[0].title()
    best_type_avg = sum(best_type[1]) / len(best_type[1]) if best_type[1] else 0.0

    # Trend calculation (first half vs second half chronologically)
    chronological = sorted(posts, key=lambda p: str(p.get("timestamp") or ""))
    trend_description = "stable"
    if len(chronological) >= 4:
        half = len(chronological) // 2
        older_avg = sum(float(p.get("engagement_rate_percent", 0.0)) for p in chronological[:half]) / half
        recent_avg = sum(float(p.get("engagement_rate_percent", 0.0)) for p in chronological[half:]) / (len(chronological) - half)
        if older_avg > 0:
            diff_pct = ((recent_avg - older_avg) / older_avg) * 100
            if diff_pct > 10:
                trend_description = f"trending upwards (+{diff_pct:.1f}% recently)"
            elif diff_pct < -10:
                trend_description = f"trending downwards ({diff_pct:.1f}% recently)"

    takeaways = [
        f"**Average Engagement:** @{username}'s posts average **{avg_rate:.2f}%** engagement rate across {len(posts)} analyzed posts ({total_likes:,} likes, {total_comments:,} comments).",
        f"**Top Performing Post:** '{top_caption}' generated **{top_eng:,}** engagements ({top_rate:.2f}% engagement rate).",
        f"**Winning Format:** **{best_type_name}s** are the highest performing media format, delivering an average engagement rate of **{best_type_avg:.2f}%**.",
        f"**Engagement Trajectory:** Audience interaction is currently **{trend_description}** across the analyzed period.",
    ]

    recommendations = [
        f"Double down on **{best_type_name}** content to maximize algorithmic distribution and organic reach.",
        f"Analyze the hook and visual style of the top post ('{top_caption}') and replicate its structure across upcoming campaigns.",
        "Maintain active community replies in the first 2 hours of posting to boost comment velocity and explore page discovery.",
    ]

    return {
        "summary": f"Analyzed {len(posts)} posts for @{username}. Overall engagement averages {avg_rate:.2f}%. Best format is {best_type_name}.",
        "key_takeaways": takeaways,
        "recommendations": recommendations,
        "benchmark": {
            "average_engagement_rate_percent": round(avg_rate, 3),
            "top_engagement_rate_percent": round(top_rate, 3),
            "total_engagements": total_likes + total_comments,
            "winning_media_type": best_type_name,
        },
    }
