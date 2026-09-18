"""Apify-specific fetch layer for the Instagram Profile Scraper actor."""

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

ACTOR_ID = "apify/instagram-profile-scraper"
TERMINAL_SUCCESS = {"SUCCEEDED"}
TERMINAL_FAILURE = {"FAILED", "ABORTED", "TIMED-OUT", "TIMED_OUT"}


class ApifyInstagramFetcher:
    """Starts, polls, and reads a single run of Apify's profile actor."""

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

    def fetch_profile(self, username: str) -> dict[str, Any]:
        """Fetch one public profile using Apify's asynchronous run lifecycle."""
        run_input = {"usernames": [username]}
        try:
            # Do not use ActorClient.call(): this deliberately exposes the async
            # lifecycle so timeout/status handling remains under this server's control.
            run = self.client.actor(ACTOR_ID).start(run_input=run_input)
            run_id = run.get("id")
            if not run_id:
                raise UpstreamServiceError("Apify started a run without returning a run ID.")

            completed_run = self._poll_run(run_id)
            dataset_id = completed_run.get("defaultDatasetId") or run.get("defaultDatasetId")
            if not dataset_id:
                raise UpstreamServiceError("Apify completed the run without a result dataset.")

            items = list(self.client.dataset(dataset_id).iterate_items())
        except (ConfigurationError, ProfileNotFoundError, RateLimitError, UpstreamServiceError):
            raise
        except Exception as exc:  # Apify SDK error types differ across versions.
            raise self._friendly_apify_error(exc) from None

        if not items:
            raise ProfileNotFoundError(
                f"No public Instagram profile data was returned for @{username}. "
                "Check the username or confirm that the account is public."
            )
        return items[0]

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
                raise UpstreamServiceError(f"Apify could not scrape this profile: {detail}")
            time.sleep(self._poll_interval_seconds)

        raise UpstreamServiceError(
            f"Apify did not finish within {int(self._timeout_seconds)} seconds. Please try again shortly."
        )

    @staticmethod
    def _friendly_apify_error(exc: Exception) -> UpstreamServiceError | RateLimitError:
        message = str(exc)
        lower_message = message.lower()
        if "429" in message or "rate limit" in lower_message or "too many request" in lower_message:
            return RateLimitError("Apify rate-limited this request. Please wait a moment and try again.")
        if "401" in message or "403" in message or "token" in lower_message:
            return UpstreamServiceError(
                "Apify rejected the request. Verify that APIFY_API_TOKEN is valid and can run this actor."
            )
        return UpstreamServiceError(
            "Apify could not retrieve Instagram data right now. Please try again shortly."
        )
