# Tool reference

All tools take `username` (required) and `platform="instagram"|"youtube"` unless noted.

## get_profile_summary
Args: `username`, `platform`. 1 scrape.
Returns `profile` (username, full_name, followers/subscribers, following, post/video count, verified, lifetime views on YouTube), `markdown_table`, `insights` (incl. follower-to-following authority ratio on Instagram).

## get_engagement_metrics
Args: `date_range=None`, `post_limit=12`. 1 scrape.
Returns per-item likes, comments, views (YouTube), media type, engagement rate; a sorted `markdown_table`; content-type breakdowns; `date_range_applied`.

## generate_dashboard
Args: `metric` (required), `chart_type=None`, `date_range=None`, `top_n=5`, `output="png"`. 1 scrape.
- `top_posts_by_engagement` — bar chart, captions/titles as labels.
- `engagement_rate_over_time` — line chart, chronological.
- `content_type_comparison` — avg engagement by format (Reels/Carousels/Images/Videos; Shorts/Video/Livestream).
- `follower_growth` — only points recorded by this server's fetches.
- `all` — delegates to `audit_profile`.
Returns image content blocks (png), `interactive_chart_spec` (spec), `markdown_table`, `insights`.

## audit_profile
Args: `date_range=None`, `post_limit=12`, `top_n=5`, `output="png"`. 1 scrape.
Account stats + all three charts + top-posts and content-type tables + executive report + recommendations, in one call.

## analyze_sentiment
Args: `post_limit=5`, `comments_per_post=30`, `date_range=None`, `output="none"`, `include_comments=False`. **2 scrapes** (profile + comments). Spend scales with `post_limit × comments_per_post`.
Key fields:
- `distribution` / `distribution_percent` — positive/neutral/negative.
- `net_sentiment_score` — positive% − negative%, −100..+100. Primary headline number.
- `average_compound` — mean VADER score, −1..+1; sensitive to a few strong comments.
- `verdict` — plain-language bucket from net score.
- `overall_label` — from average_compound; may disagree with verdict.
- `most_positive_comments`, `most_negative_comments` — quote these for "what are people saying".
- `per_post_breakdown`, `per_post_markdown`, `top_comments_markdown`.
- `comments_excluded_as_owner` — creator's own replies removed.
- `caveats` — English-only, no sarcasm, non-Latin share warnings.
`output="png"` adds a distribution chart. `include_comments=True` returns every scored comment (large; only on request).

## list_available_metrics
Args: `platform`. Free. Supported metrics, default chart types, bounds.

## get_usage_metrics
No args. Free. Invocation counts, unique callers, per-tool breakdown, errors, uptime.

## Common response fields
- `ok` — false on error, with an error message.
- `source.cache_hit` / `source.comments_cache_hit` — whether Apify was actually called.
