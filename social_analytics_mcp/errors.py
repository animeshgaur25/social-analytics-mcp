"""User-safe errors surfaced by the MCP tools."""


class SocialAnalyticsError(Exception):
    """Base error whose message is safe to return to an MCP client."""


class ConfigurationError(SocialAnalyticsError):
    """The server is missing required configuration."""


class ProfileNotFoundError(SocialAnalyticsError):
    """Apify returned no profile for the supplied public username."""


class PrivateAccountError(SocialAnalyticsError):
    """The requested profile is private."""


class RateLimitError(SocialAnalyticsError):
    """The upstream service rejected the request because of a rate limit."""


class UpstreamServiceError(SocialAnalyticsError):
    """The scraper failed without exposing implementation details to the user."""


class NoDataError(SocialAnalyticsError):
    """The requested calculation has no available data."""


class InvalidRequestError(SocialAnalyticsError):
    """The caller supplied an unsupported argument."""


class ChartRenderingError(SocialAnalyticsError):
    """Plotly could not render a chart image."""
