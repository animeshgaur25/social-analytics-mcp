"""Apify-specific fetch layer for the Instagram and YouTube scraper actors."""

from __future__ import annotations

import os
import time
from typing import Any

from apify_client import ApifyClient

from .errors import (
    ConfigurationError,
    ProfileNotFoundError,
    RateLimitError,
    UpstreamServiceError,
)
from .platforms import INSTAGRAM, YOUTUBE

ACTOR_ID = INSTAGRAM.default_actor
YOUTUBE_ACTOR_ID = YOUTUBE.default_actor
TERMINAL_SUCCESS = {"SUCCEEDED"}
TERMINAL_FAILURE = {"FAILED", "ABORTED", "TIMED-OUT", "TIMED_OUT"}


class _ApifyRunner:
    """Starts, polls, and reads a single Apify actor run."""

    service_label = "social"

    def __init__(
        self,
        token: str | None = None,
        *,
        client: ApifyClient | None = None,
        poll_interval_seconds: float | None = None,
        timeout_seconds: float | None = None,
    ) -> None:
        self._token = token if token is not None else os.getenv("APIFY_API_TOKEN", "")
        self._client = client
        self._poll_interval_seconds = poll_interval_seconds or float(
            os.getenv("APIFY_POLL_INTERVAL_SECONDS", "2")
        )
        self._timeout_seconds = timeout_seconds or float(os.getenv("APIFY_RUN_TIMEOUT_SECONDS", "180"))

    @property
    def client(self) -> ApifyClient:
        if not self._token and self._client is None:
            raise ConfigurationError(
                "APIFY_API_TOKEN is not configured. Add it to your environment and restart the server."
            )
        if self._client is None:
            self._client = ApifyClient(self._token)
        return self._client

    def _run_actor(self, actor_id: str, run_input: dict[str, Any]) -> list[dict[str, Any]]:
        try:
            # Do not use ActorClient.call(): this deliberately exposes the async
            # lifecycle so timeout/status handling remains under this server's control.
            run = self.client.actor(actor_id).start(run_input=run_input)
            run_id = run.get("id")
            if not run_id:
                raise UpstreamServiceError("Apify started a run without returning a run ID.")

            completed_run = self._poll_run(run_id)
            dataset_id = completed_run.get("defaultDatasetId") or run.get("defaultDatasetId")
            if not dataset_id:
                raise UpstreamServiceError("Apify completed the run without a result dataset.")

            return list(self.client.dataset(dataset_id).iterate_items())
        except (ConfigurationError, ProfileNotFoundError, RateLimitError, UpstreamServiceError):
            raise
        except Exception as exc:  # Apify SDK error types differ across versions.
            raise self._friendly_apify_error(exc, self.service_label) from None

    def _poll_run(self, run_id: str) -> dict[str, Any]:
        deadline = time.monotonic() + self._timeout_seconds
        while time.monotonic() < deadline:
            run = self.client.run(run_id).get()
            if not run:
                raise UpstreamServiceError("The Apify run could no longer be found.")
            status = str(run.get("status", "")).upper()
            if status in TERMINAL_SUCCESS:
                return run
            if status in TERMINAL_FAILURE:
                detail = run.get("statusMessage") or "The actor did not complete successfully."
                raise UpstreamServiceError(f"Apify could not scrape this account: {detail}")
            time.sleep(self._poll_interval_seconds)

        raise UpstreamServiceError(
            f"Apify did not finish within {int(self._timeout_seconds)} seconds. Please try again shortly."
        )

    @staticmethod
    def _friendly_apify_error(exc: Exception, service_label: str) -> UpstreamServiceError | RateLimitError:
        message = str(exc)
        lower_message = message.lower()
        if "429" in message or "rate limit" in lower_message or "too many request" in lower_message:
            return RateLimitError("Apify rate-limited this request. Please wait a moment and try again.")
        if "401" in message or "403" in message or "token" in lower_message:
            return UpstreamServiceError(
                "Apify rejected the request. Verify that APIFY_API_TOKEN is valid and can run this actor."
            )
        return UpstreamServiceError(
            f"Apify could not retrieve {service_label} data right now. Please try again shortly."
        )


class ApifyInstagramFetcher(_ApifyRunner):
    """Reads one public Instagram profile and its latest posts."""

    service_label = "Instagram"

    @property
    def actor_id(self) -> str:
        return ACTOR_ID

    def fetch_profile(self, username: str) -> dict[str, Any]:
        items = self._run_actor(ACTOR_ID, {"usernames": [username]})
        if not items:
            raise ProfileNotFoundError(
                f"No public Instagram profile data was returned for @{username}. "
                "Check the username or confirm that the account is public."
            )
        return items[0]


class ApifyYouTubeFetcher(_ApifyRunner):
    """Reads one public YouTube channel's recent videos and shorts.

    The actor emits one dataset item per video; channel-level fields such as
    subscriber count ride along on each item.
    """

    service_label = "YouTube"

    def __init__(
        self,
        token: str | None = None,
        *,
        client: ApifyClient | None = None,
        poll_interval_seconds: float | None = None,
        timeout_seconds: float | None = None,
        actor_id: str | None = None,
        max_videos: int | None = None,
        max_shorts: int | None = None,
    ) -> None:
        super().__init__(
            token,
            client=client,
            poll_interval_seconds=poll_interval_seconds,
            timeout_seconds=timeout_seconds,
        )
        self._actor_id = actor_id or os.getenv("APIFY_YOUTUBE_ACTOR_ID", YOUTUBE_ACTOR_ID)
        self._max_videos = max_videos if max_videos is not None else int(os.getenv("YOUTUBE_MAX_VIDEOS", "20"))
        self._max_shorts = max_shorts if max_shorts is not None else int(os.getenv("YOUTUBE_MAX_SHORTS", "10"))

    @property
    def actor_id(self) -> str:
        return self._actor_id

    def fetch_channel(self, channel_url: str) -> list[dict[str, Any]]:
        run_input = {
            "startUrls": [{"url": channel_url}],
            "maxResults": self._max_videos,
            "maxResultsShorts": self._max_shorts,
            "maxResultStreams": 0,
            "sortVideosBy": "NEWEST",
            "downloadSubtitles": False,
            "saveSubsToKVS": False,
        }
        items = [item for item in self._run_actor(self._actor_id, run_input) if isinstance(item, dict)]
        if not items:
            raise ProfileNotFoundError(
                f"No public YouTube data was returned for {channel_url}. "
                "Check the handle or confirm that the channel has public videos."
            )
        return items


class ApifyInstagramCommentFetcher(_ApifyRunner):
    """Reads public comments for a set of Instagram post URLs."""

    service_label = "Instagram comment"

    def __init__(self, *args: Any, actor_id: str | None = None, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._actor_id = actor_id or os.getenv(
            "APIFY_INSTAGRAM_COMMENT_ACTOR_ID", INSTAGRAM.default_comment_actor
        )

    @property
    def actor_id(self) -> str:
        return self._actor_id

    def fetch_comments(self, item_urls: list[str], limit_per_item: int) -> list[dict[str, Any]]:
        if not item_urls:
            return []
        run_input = {
            "directUrls": item_urls,
            "resultsLimit": limit_per_item,
            "includeNestedComments": False,
        }
        return [item for item in self._run_actor(self._actor_id, run_input) if isinstance(item, dict)]


class ApifyYouTubeCommentFetcher(_ApifyRunner):
    """Reads public comments for a set of YouTube video URLs."""

    service_label = "YouTube comment"

    def __init__(self, *args: Any, actor_id: str | None = None, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._actor_id = actor_id or os.getenv(
            "APIFY_YOUTUBE_COMMENT_ACTOR_ID", YOUTUBE.default_comment_actor
        )

    @property
    def actor_id(self) -> str:
        return self._actor_id

    def fetch_comments(self, item_urls: list[str], limit_per_item: int) -> list[dict[str, Any]]:
        if not item_urls:
            return []
        run_input = {
            "startUrls": [{"url": url} for url in item_urls],
            "maxComments": limit_per_item,
            "sortCommentsBy": "NEWEST_FIRST",
        }
        return [item for item in self._run_actor(self._actor_id, run_input) if isinstance(item, dict)]
