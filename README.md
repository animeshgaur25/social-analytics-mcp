# social-analytics-mcp

`social-analytics-mcp` is a production-grade Python Model Context Protocol (MCP) server for querying **Instagram and YouTube** performance analytics, generating interactive Plotly dashboards, rendering structured markdown data tables, and delivering actionable audience insights—all without opening a browser.

It uses Apify's `apify/instagram-profile-scraper` actor for public Instagram profile and post metadata, and `streamers/youtube-scraper` for public YouTube channel, video, and Shorts metadata. Metrics are computed locally and rendered as interactive Plotly visualisations (with PNG fallback rendering via Kaleido).

---

## Platforms

Every analytics tool takes a `platform` argument: `"instagram"` (default) or `"youtube"`.

| | Instagram | YouTube |
| --- | --- | --- |
| Account input | `eminem`, `@eminem`, or a profile URL | `@MrBeast`, a channel URL, or a `UC…` channel ID |
| Actor | `apify/instagram-profile-scraper` | `streamers/youtube-scraper` |
| Audience metric | Followers | Subscribers |
| Content items | Posts (Reels, Carousels, Images, Videos) | Videos (long-form, Shorts, Livestreams) |
| Engagement rate | `(likes + comments) / followers` | `(likes + comments) / views` |
| Extra fields | Follower-to-following authority ratio | Per-video view counts, lifetime channel views |

YouTube engagement rate is measured against **views** rather than subscribers, which is the industry convention — subscriber count is only used as a fallback when the actor withholds a view count.

---

## What It Exposes

| Tool | Parameters | Purpose & Output |
| --- | --- | --- |
| `audit_profile` | `username`, `date_range`, `post_limit`, `top_n`, `output`, `platform` | **All-in-one comprehensive audit**: returns account stats, all 3 dashboard views (top posts/videos, engagement trajectory, content types) with charts, formatted markdown tables, and AI recommendations in a single call. |
| `get_profile_summary` | `username`, `platform` | Returns audience, following, and item counts, verification status, authority/lifetime-views analysis, and a structured Markdown summary table. |
| `get_engagement_metrics` | `username`, `date_range`, `post_limit`, `platform` | Returns item-level metrics (likes, comments, views on YouTube, media type, engagement rate), a sorted Markdown table, and content-type breakdowns. |
| `generate_dashboard` | `username`, `metric`, `chart_type`, `date_range`, `top_n`, `output`, `platform` | Generates a styled light-theme dashboard. Supports `output="png"`, `"spec"` (Plotly JSON), or `"both"`. Use `metric="all"` to trigger the full audit. |
| `analyze_sentiment` | `username`, `platform`, `post_limit`, `comments_per_post`, `date_range`, `output`, `include_comments` | Scores **audience comments** on recent items: positive/neutral/negative split, net sentiment, per-item breakdown, most positive and negative comments, and an optional distribution chart. Scraping comments costs **extra Apify credits** — see below. |
| `list_available_metrics` | `platform` | Lists supported metrics (`engagement_rate_over_time`, `top_posts_by_engagement`, `content_type_comparison`, `follower_growth`, `all`), default chart types, and operational bounds for that platform. |

### Dashboard Metrics & Outputs

- **`all` / `audit_profile`**: Full 360-degree account audit returning all three chart views below, two data tables, and an executive markdown report in one call.
- **`top_posts_by_engagement`**: Bar chart ranking top posts/videos labeled with truncated caption or title snippets.
- **`engagement_rate_over_time`**: Line chart showing engagement trajectory across chronological posts/videos.
- **`content_type_comparison`**: Bar chart comparing average engagement by format (Reels, Carousels, Images, Videos on Instagram; Shorts, long-form Videos, Livestreams on YouTube).
- **`follower_growth`**: Line chart displaying session-tracked follower/subscriber growth across fetches.


Each dashboard call returns:
1. **Rendered charts as MCP image content blocks**: with `output="png"` (or `"both"`), each chart is delivered as a real `ImageContent` block, so clients render it natively. The base64 is deliberately *not* duplicated into the JSON payload — see below.
2. **Interactive Spec (`interactive_chart_spec`)**: Full Plotly JSON structure for rich frontends (hover cards, zoom, pan, responsive labels), via `output="spec"`.
3. **Markdown Table (`markdown_table`)**: Clean, formatted tabular presentation of the underlying data.
4. **Insights & Recommendations (`insights`)**: Takeaways including top formats, engagement rates, benchmarks, and tactical recommendations.

> **Why images are content blocks.** Returning a plain dict from a FastMCP tool serialises it to `TextContent`, so a base64 PNG arrives as an unreadable ~56KB string that is *also* duplicated into `structuredContent`. A three-chart audit cost ~175KB of text that no model could actually see as an image. The chart tools now return a `CallToolResult` carrying real `ImageContent` blocks alongside `structuredContent`, which cut the audit's text payload from ~175KB to ~5KB with no loss of structured data.

---

## Setup & Installation

### 1. Environment & Dependencies

Requires Python 3.10+:

```bash
# Clone the repository
git clone https://github.com/animeshgaur25/social-analytics-mcp.git
cd social-analytics-mcp

# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -e .
```

### 2. Configure Environment Variables

```bash
cp .env.example .env
```

Edit `.env` and set your credentials:

```bash
# Required: Apify token for Instagram and YouTube scraping
APIFY_API_TOKEN=your_apify_token_here

# Optional: Gemini API Key for AI-powered caption critique & influencer reports
GEMINI_API_KEY=your_gemini_api_key_here

# Optional: Operational settings
APIFY_POLL_INTERVAL_SECONDS=2
APIFY_RUN_TIMEOUT_SECONDS=180
PROFILE_CACHE_TTL_SECONDS=900

# Optional: YouTube actor and per-run item budget (these drive Apify credit usage)
APIFY_YOUTUBE_ACTOR_ID=streamers/youtube-scraper
YOUTUBE_MAX_VIDEOS=20
YOUTUBE_MAX_SHORTS=10
```

`YOUTUBE_MAX_VIDEOS` and `YOUTUBE_MAX_SHORTS` cap how many items each channel run pulls. Both formats are fetched so that `content_type_comparison` can contrast Shorts against long-form; set `YOUTUBE_MAX_SHORTS=0` to skip Shorts and halve the credit cost.

> **Note on Kaleido**: PNG export utilizes Kaleido 1.x. If Chromium is not automatically detected on your system, run `plotly_get_chrome` to install a local headless Chromium build.

---

## Can You Use a Gemini API Key?

**Yes!** While Apify is used to retrieve public Instagram engagement signals, a **Google Gemini API Key** (`GEMINI_API_KEY`) can be incorporated to provide generative AI capabilities:

- **Qualitative Caption & Hook Critique**: Analyzing which copywriting hooks and hashtags drive the highest retention and comments.
- **Audience Sentiment & Brand Safety**: Evaluating community reactions, sentiment tone, and brand safety for sponsorship screening.
- **Executive Influencer Briefs**: Synthesizing raw metrics into ready-to-share campaign pitch decks and collaboration strategies.

To use Gemini, add `GEMINI_API_KEY` in your `.env`. You can use Google's `google-genai` SDK or call Gemini models (`gemini-2.5-flash`, `gemini-1.5-pro`) to process the structured tables and metric outputs returned by this server.

---

## Testing with the Cristiano Ronaldo Example

The server includes end-to-end tests and CLI tools tested with Cristiano Ronaldo's public account (`@cristiano`).

### 1. Run the Automated Live Smoke Test

The test suite exercises every MCP tool via stdio, generates dashboards, and exports both PNG images and interactive Plotly JSON specs:

```bash
python tests/test_e2e.py
```

**Output:**
```text
✓ list_available_metrics
✓ get_profile_summary
✓ get_engagement_metrics
✓ generate_dashboard (engagement_rate_over_time)
✓ Wrote cristiano_engagement_rate_over_time.png and cristiano_engagement_rate_over_time.plotly.json
✓ generate_dashboard (top_posts_by_engagement)
✓ Wrote cristiano_top_posts_by_engagement.png and cristiano_top_posts_by_engagement.plotly.json
✓ generate_dashboard (content_type_comparison)
✓ Wrote cristiano_content_type_comparison.png and cristiano_content_type_comparison.plotly.json
```

### 2. Offline Component Tests

Run offline unit tests verifying data transformations, mock Apify responses, and Plotly serialization without consuming Apify credits:

```bash
python tests/test_components.py
```

---

## CLI Usage (Cristiano Ronaldo Example)

You can execute all analytics functions directly from your terminal using the `social-analytics` CLI:

### Profile Summary
```bash
social-analytics profile cristiano
```
*Output snippet:*
```json
{
  "profile": {
    "username": "cristiano",
    "full_name": "Cristiano Ronaldo",
    "followers": 679680239,
    "following": 635,
    "post_count": 4131,
    "verified": true
  },
  "markdown_table": "| Metric | Value |\n|---|---|\n| **Username** | @cristiano |\n| **Full Name** | Cristiano Ronaldo |\n| **Followers** | 679,680,239 |\n| **Following** | 635 |\n| **Posts** | 4,131 |\n| **Verified** | Yes |",
  "insights": [
    "Follower-to-following ratio is **1070362.6x**, indicating strong audience authority.",
    "Account has published **4,131** posts on Instagram.",
    "Verified status: **Verified public figure / organization**."
  ]
}
```

### Full Account Audit (Single Call)
Run the entire 360-degree audit with all 3 charts, tables, and insights:

```bash
# Returns top posts, 90-day trajectory, and format comparison in one go
social-analytics audit cristiano --output spec

# Or save images with output both
social-analytics audit cristiano --output both
```

### Engagement Metrics
Fetch post-level stats over a specified timeframe or post count:
```bash
social-analytics engagement cristiano --date-range 90d --post-limit 12
```

### Generate Individual Dashboards
Generate specific charts with optional image export (`--png-output`) and representation mode (`--output png|spec|both`):

```bash
# 1. Top Posts by Engagement (Bar chart with caption previews)
social-analytics dashboard cristiano top_posts_by_engagement --top-n 5 --output both --png-output cristiano_top_posts_by_engagement.png

# 2. Engagement Rate Over Time (Line chart)
social-analytics dashboard cristiano engagement_rate_over_time --output png --png-output cristiano_engagement_rate_over_time.png

# 3. Content Type Breakdown (Reels vs Images vs Carousels)
social-analytics dashboard cristiano content_type_comparison --output both
```

---

## YouTube Usage

Add `--platform youtube` to any command and pass a channel handle, URL, or `UC…` ID:

```bash
# Channel summary: subscribers, lifetime views, video count
social-analytics profile @MrBeast --platform youtube

# Per-video metrics including view counts
social-analytics engagement @MrBeast --platform youtube --post-limit 12

# Full 360 audit with all three charts
social-analytics audit @MrBeast --platform youtube --output spec

# Shorts vs long-form engagement comparison
social-analytics dashboard @MrBeast content_type_comparison --platform youtube --output both
```

*Sample audit output:*

```text
# Performance Audit: @MrBeast (MrBeast) · YouTube
**Subscribers:** 518,000,000 | **Lifetime views:** 140,603,012,575 | **Videos:** 1,003 | **Verified:** Yes

## 2. Content-Type Breakdown
| Content Type | Videos | Share | Avg Views | Avg Likes | Avg Comments | Avg Eng. Rate |
|---|---|---|---|---|---|---|
| Video | 8 | 66.7% | 95,438,088 | 1,912,500 | 104,782 | 2.22% |
| Short | 4 | 33.3% | 44,162,020 | 1,236,750 | 44,547 | 2.99% |
```

From an MCP client, the same thing is a `platform` argument:

```json
{ "name": "audit_profile", "arguments": { "username": "@MrBeast", "platform": "youtube" } }
```

---

## Audience Sentiment

`analyze_sentiment` scrapes the actual comment threads on an account's most recent items and scores them locally.

```bash
social-analytics sentiment cristiano --post-limit 3 --comments-per-post 30
social-analytics sentiment @MrBeast --platform youtube --post-limit 3 --output png
```

*Sample output:*

```text
| Sentiment | Comments | Share |
|---|---|---|
| Positive | 17 | 60.7% |
| Neutral | 9 | 32.1% |
| Negative | 2 | 7.1% |
```

**Cost.** This is the only tool that runs a *second* Apify actor (`apify/instagram-comment-scraper` or `streamers/youtube-comments-scraper`), so it costs extra credits on top of the profile fetch. Spend is bounded by `post_limit × comments_per_post`; both default conservatively (5 × 30). Comment payloads are cached per session, so repeat calls with the same arguments are free.

**How scoring works.** Comments are scored locally with VADER — nothing is sent to a third-party model. Stock VADER is unusable on social text: it maps 🔥 to the word "fire" and scores it **−1.4 (negative)**, while ❤️, 💯, and 🐐 resolve to multi-word descriptions absent from its lexicon and land on neutral. Since those are the most common forms of praise in comments, the defaults invert the result. `sentiment.py` therefore substitutes known emoji with controlled tokens before scoring and overlays social slang (`goat`, `banger`, `mid`, `cringe`, `w`), so VADER's negation and intensifier handling still applies.

**Known limits**, returned in the response's `caveats` field rather than buried here:
- **English-only.** Non-Latin-script comments score neutral regardless of content. The response counts them and warns when they are a meaningful share, because that inflates the neutral bucket and understates sentiment for multilingual audiences.
- **No sarcasm detection.** A lexicon cannot catch it.
- The creator's own replies are excluded (`authorIsChannelOwner` on YouTube, handle match on both), so the result measures audience reaction rather than the creator's own pinned comment.

---

## Connecting to an MCP Client

### Stdio Transport (Claude Desktop / Cursor / Antigravity)

Add the server to your MCP client configuration (e.g., `claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "social-analytics-mcp": {
      "command": "/absolute/path/to/social-analytics-mcp/.venv/bin/python",
      "args": ["-m", "social_analytics_mcp"],
      "cwd": "/absolute/path/to/social-analytics-mcp",
      "env": {
        "APIFY_API_TOKEN": "your_apify_token_here",
        "GEMINI_API_KEY": "your_gemini_api_key_here"
      }
    }
  }
}
```

---

## Google Cloud Run Deployment

The server is fully containerized and deployable to Google Cloud Run. It exposes:
- `/` — Interactive web status dashboard and tool directory.
- `/mcp` — Server-Sent Events (SSE) streamable HTTP transport for remote MCP clients.
- `/stats` — Real-time telemetry (invocations, unique callers, tool breakdown, latency).
- `/health` — Operational uptime check.

### Deploy with the Included Script:

```bash
APIFY_API_TOKEN='your-token' ./scripts/deploy_cloud_run.sh YOUR_PROJECT_ID us-central1
```

The script manages Google Secret Manager, configures IAM roles, and provisions Cloud Run with 2 CPU / 2Gi RAM for Kaleido image rendering.

**Shared cache.** Cloud Run recycles instances freely and scales horizontally, so a per-process cache is cold far more often than not — and every miss costs a 30–90s Apify run. The deploy provisions a `gs://<project>-social-analytics-cache` bucket and sets `CACHE_BACKEND=gcs`, so all instances share one cache. Lookups check local memory first and fall back to the bucket, promoting any shared hit into memory. The backend is strictly best-effort: if the bucket is unreachable, the server logs a warning and serves from memory rather than failing the call. Entries carry their own TTL (`PROFILE_CACHE_TTL_SECONDS`), and a 1-day lifecycle rule sweeps up objects that expiry already made unreadable. Local runs default to `CACHE_BACKEND=memory` and need no bucket.

**Timeouts.** `analyze_sentiment` runs two actors back to back (profile, then comments), and a YouTube channel scrape alone can take ~90s, so the deploy sets a 600s Cloud Run request timeout and a 240s per-actor Apify poll budget. Override either with `CLOUD_RUN_TIMEOUT_SECONDS` or `APIFY_RUN_TIMEOUT_SECONDS`:

```bash
CLOUD_RUN_TIMEOUT_SECONDS=900 ./scripts/deploy_cloud_run.sh YOUR_PROJECT_ID us-central1
```

---

## License

MIT License. Developed for automated social intelligence and AI influencer workflows.
