# social-analytics-mcp

`social-analytics-mcp` is a production-grade Python Model Context Protocol (MCP) server for querying Instagram performance analytics, generating interactive Plotly dashboards, rendering structured markdown data tables, and delivering actionable audience insights—all without opening Instagram.

It uses Apify's `apify/instagram-profile-scraper` actor for retrieving public profile and post metadata, computes metrics locally, and produces interactive Plotly visualisations (with lightweight PNG fallback rendering via Kaleido).

---

## What It Exposes

| Tool | Parameters | Purpose & Output |
| --- | --- | --- |
| `audit_profile` | `username`, `date_range`, `post_limit`, `top_n`, `output` | **All-in-one comprehensive audit**: returns profile stats, authority ratio, all 3 dashboard views (top posts, engagement trajectory, content types) with charts, formatted markdown tables, and AI recommendations in a single call. |
| `get_profile_summary` | `username` | Returns follower, following, and post counts, verification status, ratio authority analysis, and a structured Markdown summary table. |
| `get_engagement_metrics` | `username`, `date_range`, `post_limit` | Returns post-level metrics (likes, comments, media type, engagement rate), a sorted Markdown post table, and content-type breakdowns. |
| `generate_dashboard` | `username`, `metric`, `chart_type`, `date_range`, `top_n`, `output` | Generates a styled light-theme dashboard. Supports `output="png"`, `"spec"` (Plotly JSON), or `"both"`. Use `metric="all"` to trigger the full profile audit. |
| `list_available_metrics` | _none_ | Lists supported metrics (`engagement_rate_over_time`, `top_posts_by_engagement`, `content_type_comparison`, `follower_growth`, `all`), default chart types, and operational bounds. |

### Dashboard Metrics & Outputs

- **`all` / `audit_profile`**: Full 360-degree account audit returning all three chart views below, two data tables, and an executive markdown report in one call.
- **`top_posts_by_engagement`**: Bar chart ranking top posts labeled with truncated caption snippets.
- **`engagement_rate_over_time`**: Line chart showing engagement trajectory across chronological posts.
- **`content_type_comparison`**: Bar chart comparing average engagement by format (Reels, Carousels, Images, Videos).
- **`follower_growth`**: Line chart displaying session-tracked follower growth across fetches.


Each dashboard call returns:
1. **Interactive Spec (`interactive_chart_spec`)**: Full Plotly JSON structure for rich frontends (hover cards, zoom, pan, responsive labels).
2. **High-Res PNG (`image_png_base64`)**: Base64-encoded image for standard MCP chat clients.
3. **Markdown Table (`markdown_table`)**: Clean, formatted tabular presentation of the underlying data.
4. **Insights & Recommendations (`insights`)**: Takeaways including top formats, engagement rates, benchmarks, and tactical recommendations.

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
# Required: Apify token for Instagram scraping
APIFY_API_TOKEN=your_apify_token_here

# Optional: Gemini API Key for AI-powered caption critique & influencer reports
GEMINI_API_KEY=your_gemini_api_key_here

# Optional: Operational settings
APIFY_POLL_INTERVAL_SECONDS=2
APIFY_RUN_TIMEOUT_SECONDS=180
PROFILE_CACHE_TTL_SECONDS=900
```

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

---

## License

MIT License. Developed for automated social intelligence and AI influencer workflows.
