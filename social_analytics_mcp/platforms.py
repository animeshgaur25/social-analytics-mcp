"""Per-platform vocabulary shared by the fetch, chart, table, and insight layers."""

from __future__ import annotations

from dataclasses import dataclass

from .errors import InvalidRequestError


@dataclass(frozen=True)
class PlatformSpec:
    """Naming and formula differences between the supported networks."""

    id: str
    label: str
    default_actor: str
    account_noun: str
    item_noun: str
    item_noun_plural: str
    audience_noun: str
    caption_noun: str
    engagement_basis: str
    formats_blurb: str
    handle_example: str
    tracks_following: bool


INSTAGRAM = PlatformSpec(
    id="instagram",
    label="Instagram",
    default_actor="apify/instagram-profile-scraper",
    account_noun="profile",
    item_noun="post",
    item_noun_plural="posts",
    audience_noun="Followers",
    caption_noun="Caption",
    engagement_basis="followers",
    formats_blurb="Comparison of Reels, Carousels, Static Images, and Videos",
    handle_example="eminem",
    tracks_following=True,
)

YOUTUBE = PlatformSpec(
    id="youtube",
    label="YouTube",
    default_actor="streamers/youtube-scraper",
    account_noun="channel",
    item_noun="video",
    item_noun_plural="videos",
    audience_noun="Subscribers",
    caption_noun="Title",
    engagement_basis="views",
    formats_blurb="Comparison of Shorts, long-form Videos, and Livestreams",
    handle_example="@MrBeast",
    tracks_following=False,
)

SUPPORTED_PLATFORMS = {spec.id: spec for spec in (INSTAGRAM, YOUTUBE)}


def resolve_platform(platform: str | None) -> PlatformSpec:
    key = (platform or INSTAGRAM.id).strip().lower()
    spec = SUPPORTED_PLATFORMS.get(key)
    if spec is None:
        raise InvalidRequestError(
            f"Unsupported platform '{platform}'. Use one of: {', '.join(sorted(SUPPORTED_PLATFORMS))}."
        )
    return spec
