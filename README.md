# social-analytics-mcp

`social-analytics-mcp` is a Python MCP server for asking an AI assistant for
Instagram performance data and charts, without opening Instagram analytics.
It uses Apify's `apify/instagram-profile-scraper` actor for public profile
data, then calculates metrics locally.

Plotly is used because it provides both sides of the product experience: a
high-quality PNG for ordinary MCP clients and a portable JSON chart definition
that compatible clients can render with hover, zoom, and pan interactions.
Charts use a light theme.

## What it exposes

| Tool | Purpose |
| --- | --- |
| `get_profile_summary(username)` | Returns public profile name, bio, follower/following/post counts, and verified status. |
| `get_engagement_metrics(username, date_range, post_limit)` | Returns per-post likes, comments, image/video/carousel/reel type, engagement, and engagement rate. |
| `generate_dashboard(username, metric, chart_type, date_range)` | Returns a base64 PNG and Plotly interactive spec. `top_n` is an optional extra argument for ranked-post charts. |
| `list_available_metrics()` | Describes the server's current metrics, chart defaults, and source limitations. |

An engagement rate is returned both as an unscaled decimal matching
`(likes + comments) / followers` and as a convenience percent field. Dashboard
axes use the percent field.

Supported `date_range` values are `all`, a trailing window such as `30d`, or
an inclusive ISO range such as `2026-01-01:2026-01-31`.

## Setup

1. Create and activate a Python 3.10+ virtual environment.
2. Install the server:

   ```bash
   pip install -e .
   ```

3. Copy the example settings and add an Apify API token that may run the actor:

   ```bash
   cp .env.example .env
   ```

4. Set `APIFY_API_TOKEN` in `.env`. Do not commit this file.

Plotly uses Kaleido to export the required PNG. With Kaleido 1.x, install a
supported Chrome/Chromium browser if it is not already present; run
`plotly_get_chrome` if Kaleido reports that it cannot find one.

## Run it with an MCP client

The server speaks stdio by default:

```bash
python -m social_analytics_mcp
```

For a desktop MCP client, register the project virtual environment's Python
interpreter and the command `-m social_analytics_mcp`, with this project as its
working directory. The process must receive `APIFY_API_TOKEN` through its
environment or the `.env` file.

Example client configuration shape:

```json
{
  "mcpServers": {
    "social-analytics-mcp": {
      "command": "/absolute/path/to/.venv/bin/python",
      "args": ["-m", "social_analytics_mcp"],
      "cwd": "/absolute/path/to/social-analytics-mcp"
    }
  }
}
```

Each `generate_dashboard` response includes:

- `image_png_base64` and `image_mime_type`, which satisfy clients that display
  chart images.
- `interactive_chart_spec`, a Plotly JSON object that an interactive client
  can render without re-querying Apify.

## Deploy to Google Cloud Run

The repository includes a Cloud Run container configuration and a deployment
script. The deployed service uses MCP's Streamable HTTP transport at `/mcp`,
binds to Cloud Run's `PORT`, and keeps `APIFY_API_TOKEN` in Secret Manager.

The default deployment is **authenticated**, which prevents an exposed service
from being used to spend your Apify quota. Grant the intended callers the Cloud
Run Invoker role, then configure their MCP client with the printed endpoint
(`https://SERVICE-URL/mcp`) and Google authentication.

From the project directory, with Google Cloud CLI installed and authenticated:

```bash
APIFY_API_TOKEN='your-token' ./scripts/deploy_cloud_run.sh YOUR_PROJECT_ID YOUR_REGION
```

For example, choose a nearby Cloud Run region such as `asia-south1` only if it
matches the region you want for the service. The script enables required APIs,
creates a dedicated service account, stores/rotates the Secret Manager value,
deploys the service, and prints the endpoint.

To permit an external, unauthenticated MCP client, explicitly replace the
script's `--no-allow-unauthenticated` with `--allow-unauthenticated` and add a
separate authentication layer before production use. Public access would let
any caller trigger paid Apify jobs.

## Terminal testing

The CLI invokes the same framework-independent handlers as MCP:

```bash
social-analytics metrics
social-analytics profile eminem
social-analytics engagement eminem --date-range 90d --post-limit 12
social-analytics dashboard eminem engagement_rate_over_time --png-output eminem.png
```

Run the live test script against the public `@eminem` account:

```bash
python tests/test_e2e.py
```

It starts the server over MCP stdio, calls every exposed tool, and creates
three Plotly dashboards: engagement over time, top posts, and content-type
comparison. It writes each as both a PNG and an interactive
`*.plotly.json` specification. It is
intentionally opt-in: every fresh profile request runs the paid Apify actor.

## Design

```text
MCP tool definitions (server.py)
       ↓
Tool handlers (tools.py) ── session cache + follower snapshots
       ↓                         ↓
Apify run lifecycle (apify.py)   metric transformations (metrics.py)
                                         ↓
                              Plotly PNG + interactive spec (charts.py)
```

`apify.py` explicitly starts an actor run, polls its status until it reaches a
terminal state, then reads the run's default dataset. This makes timeout,
rate-limit, empty-result, and actor-failure messages safe and actionable
instead of leaking a traceback.

The cache is in-process and has a 15-minute default TTL. Repeated requests for
the same username—including different date ranges—reuse the same latest-post
payload. Set `PROFILE_CACHE_TTL_SECONDS` if a different freshness/cost tradeoff
is appropriate. Fresh re-fetches are retained as follower snapshots for the
session-only follower-growth chart.

## Apify data limits to plan for

- `apify/instagram-profile-scraper` returns public profile data and the latest
  posts; its current listing documents the latest **12** posts. `post_limit`
  can only narrow that returned set; it cannot fetch older posts from this
  actor. For deeper historical post coverage, add Apify's Instagram Post
  Scraper behind another source adapter.
- The selected actor returns a current follower count, not a historical series.
  `follower_growth` works only after this server has collected two fresh
  session snapshots (or after a future persistence/historical-data adapter is
  added).
- Actor runs are asynchronous and can take seconds or longer. The default MCP
  timeout is 180 seconds and can be configured with
  `APIFY_RUN_TIMEOUT_SECONDS`.
- Apify pricing, quotas, and rate limits are account/actor-plan dependent. The
  server returns a retry-friendly message for upstream rate limits, but does
  not silently retry paid runs.
- Instagram can change, omit, or delay public counters. Results should be used
  as scraped public signals, not as first-party Instagram Insights.
