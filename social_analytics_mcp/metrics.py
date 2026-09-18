"""Platform-neutral transformations and social-performance calculations."""

from __future__ import annotations

from datetime import datetime, time, timedelta, timezone
from typing import Any

from .errors import InvalidRequestError, NoDataError, PrivateAccountError


def normalize_username(username: str) -> str:
    cleaned = username.strip().removeprefix("@").rstrip("/")
    if "instagram.com/" in cleaned:
        cleaned = cleaned.split("instagram.com/", 1)[1].split("/", 1)[0]
    if not cleaned or any(char.isspace() for char in cleaned):
        raise InvalidRequestError("Provide a valid Instagram username, for example 'eminem'.")
    return cleaned.lower()


def normalize_profile(raw: dict[str, Any]) -> dict[str, Any]:
    """Map actor output into a stable, source-independent profile shape."""
    username = str(raw.get("username") or "").strip().lstrip("@")
    if not username:
        raise NoDataError("Apify returned a profile without a username.")
    if raw.get("private") is True:
        raise PrivateAccountError(
            f"@{username} is private. This server can analyse only public Instagram profiles."
        )

    followers = _nonnegative_int(raw.get("followersCount"))
    posts = [normalize_post(post, followers) for post in raw.get("latestPosts") or []]
    posts.sort(key=lambda post: post["timestamp"] or "", reverse=True)

    return {
        "username": username,
        "full_name": raw.get("fullName") or username,
        "bio": raw.get("biography") or "",
        "followers": followers,
        "following": _nonnegative_int(raw.get("followsCount")),
        "post_count": _nonnegative_int(raw.get("postsCount")),
        "verified": bool(raw.get("verified")),
        "posts": posts,
    }


def normalize_post(raw: dict[str, Any], followers: int) -> dict[str, Any]:
    likes = _nonnegative_int(raw.get("likesCount"))
    comments = _nonnegative_int(raw.get("commentsCount"))
    engagement = likes + comments
    rate = engagement / followers if followers else 0.0
    return {
        "id": str(raw.get("id") or raw.get("shortCode") or "unknown"),
        "shortcode": raw.get("shortCode") or "",
        "url": raw.get("url") or "",
        "timestamp": _iso_timestamp(raw.get("timestamp")),
        "media_type": canonical_media_type(raw),
        "likes": likes,
        "comments": comments,
        "engagement": engagement,
        # The unscaled rate follows the requested formula exactly; the percent
        # companion is for friendly display and charts.
        "engagement_rate": rate,
        "engagement_rate_percent": round(rate * 100, 4),
        "caption": raw.get("caption") or "",
    }


def canonical_media_type(post: dict[str, Any]) -> str:
    raw_type = str(post.get("type") or "").lower()
    product_type = str(post.get("productType") or "").lower()
    if product_type in {"clips", "reels"} or raw_type in {"reel", "clips"}:
        return "reel"
    if raw_type in {"sidecar", "carousel", "album"}:
        return "carousel"
    if raw_type in {"video", "igtv"}:
        return "video"
    return "image"


def select_posts(posts: list[dict[str, Any]], date_range: str | None, post_limit: int) -> tuple[list[dict[str, Any]], str]:
    if post_limit < 1:
        raise InvalidRequestError("post_limit must be at least 1.")
    start, end, label = parse_date_range(date_range)
    selected = []
    for post in posts:
        timestamp = parse_timestamp(post.get("timestamp"))
        if timestamp is None:
            continue
        if (start is None or timestamp >= start) and (end is None or timestamp <= end):
            selected.append(post)
    return selected[:post_limit], label


def parse_date_range(date_range: str | None) -> tuple[datetime | None, datetime | None, str]:
    """Accept all, trailing day windows (30d), or inclusive ISO date ranges."""
    if not date_range or date_range.strip().lower() == "all":
        return None, None, "all available posts"
    value = date_range.strip().lower()
    if value.endswith("d") and value[:-1].isdigit():
        days = int(value[:-1])
        if days < 1:
            raise InvalidRequestError("A relative date range must be at least 1d, for example '30d'.")
        return datetime.now(timezone.utc) - timedelta(days=days), None, f"last {days} days"
    if ":" in value:
        start_text, end_text = value.split(":", 1)
        try:
            start = datetime.combine(datetime.fromisoformat(start_text).date(), time.min, tzinfo=timezone.utc)
            end = datetime.combine(datetime.fromisoformat(end_text).date(), time.max, tzinfo=timezone.utc)
        except ValueError as exc:
            raise InvalidRequestError(
                "date_range must be 'all', a window such as '30d', or 'YYYY-MM-DD:YYYY-MM-DD'."
            ) from exc
        if start > end:
            raise InvalidRequestError("The date range start must not be after its end.")
        return start, end, f"{start_text} to {end_text}"
    raise InvalidRequestError(
        "date_range must be 'all', a window such as '30d', or 'YYYY-MM-DD:YYYY-MM-DD'."
    )


def average_engagement_rate(posts: list[dict[str, Any]]) -> float:
    if not posts:
        return 0.0
    return round(sum(post["engagement_rate"] for post in posts) / len(posts), 6)


def _nonnegative_int(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def _iso_timestamp(value: Any) -> str | None:
    timestamp = parse_timestamp(value)
    return timestamp.isoformat() if timestamp else None


def parse_timestamp(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.replace(tzinfo=parsed.tzinfo or timezone.utc).astimezone(timezone.utc)
