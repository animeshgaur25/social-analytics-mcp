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

Every tool takes `platform="instagram"` (default) or `"youtube"`. Parameters are listed as `name=default`; `username` is always required.

| Tool | Parameters | Apify cost | Purpose & Output |
| --- | --- | --- | --- |
| `audit_profile` | `date_range=None`, `post_limit=12`, `top_n=5`, `output="png"`, `platform="instagram"` | 1 actor run | **All-in-one comprehensive audit**: account stats, all 3 dashboard views (top posts/videos, engagement trajectory, content types), formatted Markdown tables, and AI recommendations in a single call. Charts return as **image content blocks**. |
| `get_profile_summary` | `platform="instagram"` | 1 actor run | Audience, following, and item counts, verification status, authority ratio (Instagram) or lifetime views (YouTube), and a structured Markdown summary table. |
| `get_engagement_metrics` | `date_range=None`, `post_limit=12`, `platform="instagram"` | 1 actor run | Item-level metrics (likes, comments, views on YouTube, media type, engagement rate), a sorted Markdown table, and content-type breakdowns. |
| `generate_dashboard` | `metric` *(required)*, `chart_type=None`, `date_range=None`, `top_n=5`, `output="png"`, `platform="instagram"` | 1 actor run | One styled light-theme chart. `output="png"` returns an **image content block**, `"spec"` a Plotly JSON spec, `"both"` for both. `metric="all"` delegates to the full audit. |
| `analyze_sentiment` | `post_limit=5`, `comments_per_post=30`, `date_range=None`, `output="none"`, `include_comments=False`, `platform="instagram"` | **2 actor runs** | Scores **audience comments**: positive/neutral/negative split, net sentiment, per-item breakdown, strongest praise and criticism, accuracy `caveats`, and an optional distribution chart. The only tool that runs a second actor — see [Audience Sentiment](#audience-sentiment). |
| `list_available_metrics` | `platform="instagram"` | none | Supported metrics (`engagement_rate_over_time`, `top_posts_by_engagement`, `content_type_comparison`, `follower_growth`, `all`), default chart types, and operational bounds for that platform. |
| `get_usage_metrics` | *none* | none | Live telemetry: invocation counts, unique callers, per-tool breakdown, error counts, and uptime. Same data as the `/stats` endpoint. |

A cached account costs **no** actor run at all — see [Shared cache](#google-cloud-run-deployment). Responses carry `source.cache_hit` so you can tell which calls actually hit Apify.

### Sample Prompts

Once the server is connected, you can just ask in plain language — the model picks the tool and the `platform`. Naming the network ("on YouTube") or passing a handle like `@MrBeast` is enough to switch platforms.

**Profile and channel basics**

| Ask | Calls |
| --- | --- |
| "How many followers does @cristiano have on Instagram?" | `get_profile_summary` |
| "Give me a summary of the MrBeast YouTube channel." | `get_profile_summary` *(youtube)* |
| "Is @eminem verified, and what's his follower-to-following ratio?" | `get_profile_summary` |
| "How many lifetime views does @MrBeast's channel have?" | `get_profile_summary` *(youtube)* |

**Engagement**

| Ask | Calls |
| --- | --- |
| "What's the average engagement rate on @cristiano's last 12 posts?" | `get_engagement_metrics` |
| "Show me per-video likes, comments and views for @MrBeast." | `get_engagement_metrics` *(youtube)* |
| "Which of @eminem's posts from the last 30 days performed best?" | `get_engagement_metrics` with `date_range="30d"` |
| "Compare engagement on posts between 2026-01-01 and 2026-03-31 for @cristiano." | `get_engagement_metrics` with an ISO range |

**Charts**

| Ask | Calls |
| --- | --- |
| "Chart @cristiano's engagement rate over time." | `generate_dashboard` → `engagement_rate_over_time` |
| "Show me @eminem's top 5 posts by engagement as a bar chart." | `generate_dashboard` → `top_posts_by_engagement` |
| "Do Reels beat carousels for @cristiano?" | `generate_dashboard` → `content_type_comparison` |
| "Are Shorts or long-form videos better for @MrBeast?" | `generate_dashboard` → `content_type_comparison` *(youtube)* |
| "Give me that chart as an interactive Plotly spec instead of an image." | same, with `output="spec"` |
| "What metrics can I chart for YouTube?" | `list_available_metrics` *(youtube)* |

**Full audit**

| Ask | Calls |
| --- | --- |
| "Run a full audit on @cristiano." | `audit_profile` |
| "Give me a complete 360 report on the MrBeast channel." | `audit_profile` *(youtube)* |
| "I'm pitching @eminem for a campaign — everything you've got." | `audit_profile` |

**Audience sentiment**

| Ask | Calls |
| --- | --- |
| "How do people feel about @MrBeast's recent videos?" | `analyze_sentiment` *(youtube)* |
| "Is the comment sentiment on @cristiano's last 3 posts positive or negative?" | `analyze_sentiment` with `post_limit=3` |
| "What are people complaining about in @eminem's comments?" | `analyze_sentiment` — read `most_negative_comments` |
| "Check sentiment on @MrBeast and chart the breakdown." | `analyze_sentiment` with `output="png"` |
| "Is this account safe to sponsor? Check audience reaction." | `audit_profile` + `analyze_sentiment` |

**Operations**

| Ask | Calls |
| --- | --- |
| "How many times has this server been called today?" | `get_usage_metrics` |
| "Which tool is erroring most?" | `get_usage_metrics` |

**Multi-step asks** — the model chains tools on its own:

- "Compare @cristiano and @eminem on engagement rate and tell me who to pick." → two `get_engagement_metrics` calls
- "Audit @MrBeast on YouTube, then check whether the comments back up the numbers." → `audit_profile` then `analyze_sentiment`
- "Which format should @cristiano post more of, and do commenters agree?" → `generate_dashboard` then `analyze_sentiment`

> Sentiment asks scrape comments and cost extra Apify credits. If you want a cheap answer, say so — "just use the last 2 posts, 10 comments each" maps to `post_limit=2, comments_per_post=10`.

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

### From an MCP client

In practice you just ask — *"How do people feel about @MrBeast's last couple of videos? Keep it cheap, 15 comments each."* — and the model issues this call:

```json
{
  "name": "analyze_sentiment",
  "arguments": {
    "username": "@MrBeast",
    "platform": "youtube",
    "post_limit": 2,
    "comments_per_post": 15
  }
}
```

Abridged response (real values from a live run against the deployed service):

```json
{
  "ok": true,
  "platform": "youtube",
  "username": "MrBeast",
  "item_noun": "video",
  "engine": "vaderSentiment with an emoji and social-slang lexicon overlay",
  "source": {
    "provider": "Apify",
    "actor": "streamers/youtube-scraper",
    "comment_actor": "streamers/youtube-comments-scraper",
    "cache_hit": false,
    "comments_cache_hit": false
  },
  "posts_analyzed": 2,
  "comments_fetched": 30,
  "comments_analyzed": 28,
  "comments_excluded_as_owner": 2,
  "distribution":         { "positive": 17, "neutral": 9, "negative": 2 },
  "distribution_percent": { "positive": 60.7, "neutral": 32.1, "negative": 7.1 },
  "average_compound": 0.4333,
  "net_sentiment_score": 53.6,
  "overall_label": "positive",
  "verdict": "overwhelmingly positive",
  "most_positive_comments": [
    {
      "text": "sick video mr beast. You're changing lives and inspiring...",
      "author": "a",
      "likes": 0,
      "sentiment": "positive",
      "sentiment_score": 0.8519,
      "item_url": "https://www.youtube.com/watch?v=v9QtM6qnG50",
      "is_owner": false
    }
  ],
  "most_negative_comments": ["..."],
  "per_post_breakdown": ["..."],
  "markdown_table": "| Sentiment | Comments | Share |...",
  "per_post_markdown": "| # | Title | Comments | Pos | Neu | Neg | Net | Avg |...",
  "top_comments_markdown": "| Sentiment | Score | Likes | Comment |...",
  "insights": ["..."],
  "recommendations": ["..."],
  "caveats": ["Scoring is English-only..."]
}
```

`markdown_table` renders as:

```text
| Sentiment | Comments | Share |
|---|---|---|
| Positive | 17 | 60.7% |
| Neutral | 9 | 32.1% |
| Negative | 2 | 7.1% |
```

### From the CLI

```bash
# Instagram, default 5 posts x 30 comments
social-analytics sentiment cristiano

# YouTube, smaller sample plus a distribution chart
social-analytics sentiment @MrBeast --platform youtube --post-limit 3 --output png

# Return every scored comment, not just the highlights
social-analytics sentiment cristiano --post-limit 2 --include-comments
```

### Reading the numbers

| Field | Meaning |
| --- | --- |
| `distribution_percent` | Share of comments in each bucket. Start here. |
| `net_sentiment_score` | `positive% − negative%`, so it ignores the neutral mass that dominates emoji-only threads. Ranges −100 to +100. |
| `average_compound` | Mean VADER compound score, −1 to +1. Sensitive to a few very strong comments. |
| `verdict` | Plain-language bucket derived from `net_sentiment_score`. |
| `overall_label` | Classification of `average_compound`. |
| `comments_excluded_as_owner` | Creator's own replies, dropped before scoring. |

> Note that `verdict` and `overall_label` answer slightly different questions and **can disagree** — a thread with equal positive and negative counts but stronger positive wording yields `net_sentiment_score: 0.0` (`verdict: "mixed or neutral"`) alongside `overall_label: "positive"`. Prefer `distribution_percent` and `net_sentiment_score` for reporting; treat `overall_label` as a secondary signal about intensity rather than balance.

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

**Shared cache.** Cloud Run recycles instances freely and scales horizontally, so a per-process cache is cold far more often than not — and every miss costs an Apify run. The deploy provisions a `gs://<project>-social-analytics-cache` bucket and sets `CACHE_BACKEND=gcs`, so all instances share one cache. Lookups check local memory first and fall back to the bucket, promoting any shared hit into memory. The backend is strictly best-effort: if the bucket is unreachable, the server logs a warning and serves from memory rather than failing the call. Entries carry their own TTL (`PROFILE_CACHE_TTL_SECONDS`), and a 1-day lifecycle rule sweeps up objects that expiry already made unreadable. Local runs default to `CACHE_BACKEND=memory` and need no bucket.

*Measured against the deployed service:*

| Call | Latency | `cache_hit` |
| --- | --- | --- |
| `get_profile_summary` — cold (Apify run) | 8.37s | `false` |
| `get_profile_summary` — warm (cache) | **0.38s** | `true` |

That is a ~22x speedup, but read it in context: a profile scrape is one of the *lighter* Apify calls. A YouTube channel scrape took ~60–96s and `analyze_sentiment` ~96s in the same environment, so the absolute seconds saved on those is far larger while the ratio varies.

The shared read path was verified directly rather than inferred: a cache entry was planted in the bucket for a handle that does not exist on Instagram, and the deployed service returned it in 2.75s with `cache_hit: true`. Without a bucket read it would have fallen through to Apify and errored, so this isolates the shared path from an ordinary in-process hit.

**Timeouts.** `analyze_sentiment` runs two actors back to back (profile, then comments), and a YouTube channel scrape alone can take ~90s, so the deploy sets a 600s Cloud Run request timeout and a 240s per-actor Apify poll budget. Override either with `CLOUD_RUN_TIMEOUT_SECONDS` or `APIFY_RUN_TIMEOUT_SECONDS`:

```bash
CLOUD_RUN_TIMEOUT_SECONDS=900 ./scripts/deploy_cloud_run.sh YOUR_PROJECT_ID us-central1
```

---

## License

MIT License. Developed for automated social intelligence and AI influencer workflows.
