---
name: social-analytics
description: Analyse public Instagram profiles and YouTube channels with the social-analytics MCP server — follower/subscriber stats, engagement rates, top posts, Reels-vs-carousel or Shorts-vs-long-form comparisons, charts, full audits, and audience comment sentiment. Use whenever the user asks about an Instagram account or YouTube channel's performance, wants to vet or compare creators/influencers for a campaign or sponsorship, asks "how are people reacting to X's posts", or wants an influencer report — even if they don't mention the MCP server or tool names.
---

# Social analytics (Instagram + YouTube)

This skill drives the `social-analytics-mcp` server. The server does the scraping (via Apify) and the maths; your job is to pick the cheapest tool that answers the question, pass the right arguments, and turn the response into a clear answer.

If none of the tools below are available, the MCP server isn't connected. Say so and point the user at the setup steps in this plugin's README rather than guessing numbers.

## Every call costs money — choose deliberately

Each tool except `list_available_metrics` and `get_usage_metrics` triggers a paid Apify scrape unless the account is cached (responses report `source.cache_hit`). `analyze_sentiment` runs **two** scrapes. YouTube scrapes take ~60–90 s.

So:
- Use the **narrowest** tool that answers the question. Follower count → `get_profile_summary`, not `audit_profile`.
- If the user wants several views of one account (stats + charts + recommendations), call `audit_profile` once instead of three `generate_dashboard` calls.
- Only call `analyze_sentiment` when the question is actually about audience reaction, brand safety, or "what are people saying". Honour any "keep it cheap" hint by lowering `post_limit` and `comments_per_post`.
- Don't re-call a tool just to reformat; the response already has Markdown tables.

## Choosing the platform and handle

Every tool takes `platform`: `"instagram"` (default) or `"youtube"`.
- "on YouTube", "channel", "videos", "Shorts", "subscribers", a `youtube.com` URL or a `UC…` ID → `platform="youtube"`.
- Otherwise Instagram. If the account name is ambiguous across both (e.g. "MrBeast") and the user didn't say, pick the platform implied by the wording (followers/posts/Reels → Instagram), and say which one you used.
- Pass the handle as the user gave it (`cristiano`, `@MrBeast`, or a profile URL); the server normalises it.

## Tool picker

| User wants | Tool | Key args |
|---|---|---|
| Followers/subscribers, verified, following, post count, lifetime views | `get_profile_summary` | — |
| Engagement rate, per-post likes/comments/views, best posts in a period | `get_engagement_metrics` | `post_limit` (12), `date_range` |
| One specific chart | `generate_dashboard` | `metric`, `top_n`, `output` |
| "Full audit", "everything", campaign pitch, 360 report | `audit_profile` | `post_limit`, `top_n`, `output` |
| Comment sentiment, complaints, brand safety | `analyze_sentiment` | `post_limit` (5), `comments_per_post` (30) |
| Which charts exist | `list_available_metrics` | — (free) |
| Server call counts / error rates | `get_usage_metrics` | — (free) |

`generate_dashboard` metrics: `top_posts_by_engagement`, `engagement_rate_over_time`, `content_type_comparison`, `follower_growth`, `all` (= `audit_profile`). Call `list_available_metrics` first only if you're unsure a metric exists for that platform.

`date_range` formats: `"30d"` (trailing window), `"YYYY-MM-DD:YYYY-MM-DD"` (inclusive), or `"all"`/omitted. Convert "last month" → `"30d"`, "Q1 2026" → `"2026-01-01:2026-03-31"`.

`output`: `"png"` (default — charts come back as images the user sees), `"spec"` (Plotly JSON, for embedding in a web page), `"both"`. Use `"spec"` only when the user asks for interactive/embeddable charts.

Full argument details and response fields: `references/tools.md`.

## Reading results correctly

- **Engagement rate means different things per platform.** Instagram: `(likes + comments) / followers`. YouTube: `(likes + comments) / views`. Never compare an Instagram rate with a YouTube rate as if they were the same metric — say so if the user asks for that comparison.
- **Sentiment:** lead with `distribution_percent` and `net_sentiment_score` (−100 to +100). `verdict` and `overall_label` can disagree; treat `overall_label` as intensity, not balance. Always pass on the `caveats` that matter (English-only scoring, no sarcasm detection, small samples).
- **Sample size:** results cover only the most recent N items (`post_limit`), not the whole account history. Mention the sample when drawing conclusions ("across the last 12 posts…").
- `follower_growth` only has points from fetches made by this server, so it's often flat or sparse for a new account — explain that rather than reading it as zero growth.
- Use the response's `insights` and `recommendations` as raw material, but check them against the numbers and rewrite them in your own words.

## Answer shape

Lead with the direct answer in one or two sentences, then the supporting table (reuse the response's `markdown_table`, trimmed to what matters), then any charts, then 2–4 concrete recommendations if the user is making a decision. For creator comparisons or campaign vetting, use the templates in `references/report-templates.md`.

## Multi-account and multi-step asks

- **Compare creators:** one `get_engagement_metrics` per account (same `platform`, `post_limit` and `date_range` for a fair comparison), then a side-by-side table.
- **"Is X safe to sponsor?":** `audit_profile` + `analyze_sentiment`, then the vetting template.
- **"Which format should X post more of, and do commenters agree?":** `generate_dashboard(metric="content_type_comparison")` then `analyze_sentiment`.

## Errors

- Account not found / private → tell the user; Instagram data is public-profile only.
- Timeout on YouTube or sentiment → retry once with smaller `post_limit`; the retry may hit the cache.
- Invalid `date_range` → fix the format and retry; don't ask the user.
