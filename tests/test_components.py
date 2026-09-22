"""Offline checks for the Apify lifecycle, transformations, and session cache."""

from __future__ import annotations

import json
from pathlib import Path

from social_analytics_mcp.apify import ApifyInstagramFetcher, ApifyYouTubeFetcher
from social_analytics_mcp.charts import ChartGenerator
from social_analytics_mcp.metrics import normalize_channel_handle, normalize_profile
from social_analytics_mcp.tools import SocialAnalyticsTools


YOUTUBE_ITEMS = [
    {
        "id": "vid1",
        "title": "I Built a Full Studio in 24 Hours",
        "url": "https://www.youtube.com/watch?v=vid1",
        "type": "video",
        "date": "2026-09-01T12:00:00.000Z",
        "duration": "14:02",
        "viewCount": 2_400_000,
        "likes": 180_000,
        "commentsCount": 9_400,
        "channelName": "Creator Labs",
        "channelUsername": "@creatorlabs",
        "channelUrl": "https://www.youtube.com/@creatorlabs",
        "channelDescription": "Build logs and studio teardowns.",
        "numberOfSubscribers": 5_100_000,
        "channelTotalVideos": 412,
        "channelTotalViews": "1,204,000,000 views",
        "isChannelVerified": True,
    },
    {
        "id": "vid2",
        "title": "60 second desk tour",
        "url": "https://www.youtube.com/shorts/vid2",
        "type": "shorts",
        "date": "2026-08-20T09:30:00.000Z",
        "duration": "0:58",
        "viewCount": 890_000,
        "likes": 96_000,
        "commentsCount": 2_100,
        "channelName": "Creator Labs",
        "channelUsername": "@creatorlabs",
        "numberOfSubscribers": 5_100_000,
    },
    {
        "id": "vid3",
        "title": "Why we scrapped the rebuild",
        "url": "https://www.youtube.com/watch?v=vid3",
        "type": "video",
        "date": "2026-08-02T18:15:00.000Z",
        "duration": "22:41",
        "viewCount": 640_000,
        "likes": 31_000,
        "commentsCount": 4_800,
        "channelName": "Creator Labs",
        "channelUsername": "@creatorlabs",
        "numberOfSubscribers": 5_100_000,
    },
]


class FakeActor:
    def start(self, *, run_input: dict) -> dict:
        assert run_input == {"usernames": ["eminem"]}
        return {"id": "run-1"}


class FakeYouTubeActor:
    def start(self, *, run_input: dict) -> dict:
        assert run_input["startUrls"] == [{"url": "https://www.youtube.com/@creatorlabs"}]
        assert run_input["sortVideosBy"] == "NEWEST"
        return {"id": "run-1"}


class FakeRun:
    def __init__(self) -> None:
        self.calls = 0

    def get(self) -> dict:
        self.calls += 1
        if self.calls == 1:
            return {"id": "run-1", "status": "RUNNING"}
        return {"id": "run-1", "status": "SUCCEEDED", "defaultDatasetId": "dataset-1"}


class FakeDataset:
    def __init__(self, item: dict) -> None:
        self.item = item

    def iterate_items(self):
        yield self.item


class FakeApifyClient:
    def __init__(self, item: dict) -> None:
        self.run_client = FakeRun()
        self.item = item

    def actor(self, actor_id: str) -> FakeActor:
        assert actor_id == "apify/instagram-profile-scraper"
        return FakeActor()

    def run(self, run_id: str) -> FakeRun:
        assert run_id == "run-1"
        return self.run_client

    def dataset(self, dataset_id: str) -> FakeDataset:
        assert dataset_id == "dataset-1"
        return FakeDataset(self.item)


class FakeYouTubeDataset:
    def __init__(self, items: list[dict]) -> None:
        self.items = items

    def iterate_items(self):
        yield from self.items


class FakeYouTubeClient:
    def __init__(self, items: list[dict]) -> None:
        self.run_client = FakeRun()
        self.items = items

    def actor(self, actor_id: str) -> FakeYouTubeActor:
        assert actor_id == "streamers/youtube-scraper"
        return FakeYouTubeActor()

    def run(self, run_id: str) -> FakeRun:
        assert run_id == "run-1"
        return self.run_client

    def dataset(self, dataset_id: str) -> FakeYouTubeDataset:
        assert dataset_id == "dataset-1"
        return FakeYouTubeDataset(self.items)


def main() -> None:
    fixture_path = Path(__file__).parents[2] / "backend" / "Apify sample response" / "dataset_instagram-profile-scraper_2026-04-18_18-46-03-585 (1).json"
    fixture = json.loads(fixture_path.read_text())[0]
    fetcher = ApifyInstagramFetcher(
        client=FakeApifyClient(fixture), poll_interval_seconds=0.001, timeout_seconds=1
    )
    raw = fetcher.fetch_profile("eminem")
    assert raw["username"] == fixture["username"]

    tools = SocialAnalyticsTools(fetcher=fetcher)
    summary = tools.get_profile_summary("eminem")
    engagement = tools.get_engagement_metrics("eminem", "all", 3)
    assert summary["ok"], summary
    assert engagement["ok"], engagement
    assert engagement["posts_returned"] == 3, engagement
    assert all("engagement_rate" in post for post in engagement["posts"])

    # Verify single-call audit_profile
    audit = tools.audit_profile("eminem", post_limit=5, top_n=3, output="spec")
    assert audit["ok"], audit
    assert "top_posts_by_engagement" in audit["dashboards"]
    assert "engagement_rate_over_time" in audit["dashboards"]
    assert "content_type_comparison" in audit["dashboards"]
    assert "audit_markdown_report" in audit
    assert len(audit["insights"]) > 0

    # Verify metric="all" delegates to audit
    all_dash = tools.generate_dashboard("eminem", metric="all", top_n=3, output="spec")
    assert all_dash["ok"], all_dash
    assert "dashboards" in all_dash

    verify_plotly_charts(fixture)
    verify_youtube()
    print("Offline component tests passed.")


def verify_youtube() -> None:
    """Exercise the YouTube path end to end against a faked actor dataset."""
    assert normalize_channel_handle("https://www.youtube.com/@MrBeast/videos") == "@MrBeast"
    assert normalize_channel_handle("MrBeast") == "@MrBeast"
    assert normalize_channel_handle("UCX6OQ3DkcsbYNE6H8uQQuVA") == "channel/UCX6OQ3DkcsbYNE6H8uQQuVA"
    assert normalize_channel_handle("youtube.com/c/Creators") == "c/Creators"

    fetcher = ApifyYouTubeFetcher(
        client=FakeYouTubeClient(YOUTUBE_ITEMS), poll_interval_seconds=0.001, timeout_seconds=1
    )
    tools = SocialAnalyticsTools(youtube_fetcher=fetcher)

    summary = tools.get_profile_summary("@creatorlabs", platform="youtube")
    assert summary["ok"], summary
    assert summary["platform"] == "youtube"
    assert summary["profile"]["subscribers"] == 5_100_000
    assert summary["profile"]["channel_total_views"] == 1_204_000_000, summary["profile"]
    assert "Subscribers" in summary["markdown_table"]
    assert "Following" not in summary["markdown_table"]

    engagement = tools.get_engagement_metrics("@creatorlabs", "all", 10, platform="youtube")
    assert engagement["ok"], engagement
    assert engagement["posts_returned"] == 3, engagement
    assert engagement["engagement_rate_basis"] == "views"
    assert "Views" in engagement["markdown_table"]
    # (180000 + 9400) / 2400000
    top = next(p for p in engagement["posts"] if p["id"] == "vid1")
    assert abs(top["engagement_rate"] - (189_400 / 2_400_000)) < 1e-9, top
    assert {p["media_type"] for p in engagement["posts"]} == {"video", "short"}

    audit = tools.audit_profile("@creatorlabs", post_limit=5, top_n=2, output="spec", platform="youtube")
    assert audit["ok"], audit
    assert set(audit["dashboards"]) == {
        "top_posts_by_engagement",
        "engagement_rate_over_time",
        "content_type_comparison",
    }
    assert "authority_ratio" not in audit["profile"]
    assert "Subscribers:" in audit["audit_markdown_report"]
    assert audit["benchmark"]["engagement_rate_basis"] == "views"

    metrics = tools.list_available_metrics(platform="youtube")
    assert metrics["ok"], metrics
    assert metrics["metrics"][0]["description"].endswith("for each returned video.")

    bad = tools.get_profile_summary("@creatorlabs", platform="tiktok")
    assert not bad["ok"] and "Unsupported platform" in bad["error"]["message"], bad
    print("YouTube scraper path: passed")



def verify_plotly_charts(fixture: dict) -> None:
    """Create each dashboard figure and verify it serialises for interactivity."""
    profile = normalize_profile(fixture)
    generator = ChartGenerator()
    common = {"username": profile["username"], "posts": profile["posts"], "top_n": 5}
    snapshots = [
        {"timestamp": "2026-01-01T00:00:00+00:00", "followers": max(0, profile["followers"] - 100)},
        {"timestamp": "2026-02-01T00:00:00+00:00", "followers": profile["followers"]},
    ]
    expected = {
        "follower_growth": "line",
        "engagement_rate_over_time": "line",
        "top_posts_by_engagement": "bar",
        "content_type_comparison": "bar",
    }
    for metric, expected_type in expected.items():
        figure, chart_type = generator.build_figure(
            metric=metric,
            follower_history=snapshots,
            chart_type=None,
            **common,
        )
        assert chart_type == expected_type
        assert figure.data, f"{metric} did not create a Plotly trace"
        assert figure.to_plotly_json()["data"], f"{metric} is not serialisable as Plotly JSON"
    print("Plotly dashboard figures: passed")


if __name__ == "__main__":
    main()
