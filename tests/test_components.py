"""Offline checks for the Apify lifecycle, transformations, and session cache."""

from __future__ import annotations

import json
from pathlib import Path

from social_analytics_mcp.apify import ApifyInstagramFetcher
from social_analytics_mcp.charts import ChartGenerator
from social_analytics_mcp.metrics import normalize_profile
from social_analytics_mcp.tools import SocialAnalyticsTools


class FakeActor:
    def start(self, *, run_input: dict) -> dict:
        assert run_input == {"usernames": ["eminem"]}
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
    print("Offline component tests passed.")



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
