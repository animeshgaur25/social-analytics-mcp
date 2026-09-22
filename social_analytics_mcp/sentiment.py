"""Local sentiment scoring for social comments, tuned for emoji and platform slang.

VADER ships a general-purpose lexicon that misreads social media badly: it maps
the fire emoji to the word "fire" and scores it -1.4, while the heart, hundred,
and goat emoji resolve to multi-word descriptions that are absent from the
lexicon and therefore land on neutral. Since those are the most common forms of
praise in comments, the defaults invert the result.

Known emoji are substituted with controlled single tokens before scoring so that
VADER's negation and intensifier handling still applies to them.
"""

from __future__ import annotations

import re
from typing import Any

from .errors import ConfigurationError

# Emoji mapped to a private token and the valence that token carries.
EMOJI_SENTIMENT: dict[str, tuple[str, float]] = {
    "🔥": ("satok_fire", 2.4),
    "❤": ("satok_love", 3.0),
    "🧡": ("satok_love", 3.0),
    "💛": ("satok_love", 3.0),
    "💚": ("satok_love", 3.0),
    "💙": ("satok_love", 3.0),
    "💜": ("satok_love", 3.0),
    "🖤": ("satok_love", 2.0),
    "💖": ("satok_love", 3.0),
    "💕": ("satok_love", 2.8),
    "💗": ("satok_love", 2.8),
    "😍": ("satok_adore", 3.0),
    "🥰": ("satok_adore", 3.0),
    "😻": ("satok_adore", 2.8),
    "💯": ("satok_hundred", 2.6),
    "🐐": ("satok_goat", 2.5),
    "👑": ("satok_crown", 2.2),
    "🙌": ("satok_praise", 2.2),
    "👏": ("satok_clap", 2.2),
    "💪": ("satok_strong", 1.8),
    "👍": ("satok_thumbsup", 1.8),
    "😁": ("satok_grin", 1.8),
    "😃": ("satok_grin", 1.8),
    "😄": ("satok_grin", 1.9),
    "🤩": ("satok_star", 2.6),
    "🤣": ("satok_laugh", 1.8),
    "😂": ("satok_laugh", 1.6),
    "✨": ("satok_sparkle", 1.6),
    "🎉": ("satok_party", 2.0),
    "😢": ("satok_sad", -1.6),
    "😞": ("satok_sad", -1.8),
    "😠": ("satok_angry", -2.4),
    "😡": ("satok_angry", -2.8),
    "🤬": ("satok_angry", -3.0),
    "🤮": ("satok_vomit", -3.0),
    "🤢": ("satok_vomit", -2.4),
    "👎": ("satok_thumbsdown", -2.4),
    "💩": ("satok_poo", -2.5),
    "🤡": ("satok_clown", -2.0),
    "🙄": ("satok_eyeroll", -1.6),
    "😴": ("satok_boring", -1.4),
    "💔": ("satok_heartbreak", -2.2),
}

# Social usage that the general lexicon either misses or scores backwards.
SLANG_SENTIMENT: dict[str, float] = {
    "fire": 2.0,          # VADER ships -1.4; in comments this is praise
    "goat": 2.5,
    "legend": 2.4,
    "legendary": 2.6,
    "banger": 2.4,
    "iconic": 2.2,
    "slay": 2.2,
    "slaps": 2.0,
    "peak": 1.8,
    "insane": 1.6,        # overwhelmingly positive in this register
    "sick": 1.2,
    "dope": 2.0,
    "goated": 2.6,
    "respect": 2.0,
    "masterpiece": 3.0,
    "w": 1.5,
    "trash": -2.4,
    "mid": -1.2,
    "cringe": -2.0,
    "overrated": -1.8,
    "flop": -2.0,
    "scam": -2.8,
    "clickbait": -2.2,
    "boring": -1.8,
    "unwatchable": -2.6,
    "ratio": -1.2,
}

POSITIVE_THRESHOLD = 0.05
NEGATIVE_THRESHOLD = -0.05

_VARIATION_SELECTOR = "️"
_analyzer = None


def _get_analyzer():
    global _analyzer
    if _analyzer is None:
        try:
            from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
        except ImportError as exc:
            raise ConfigurationError(
                "vaderSentiment is not installed. Install the project dependencies and restart the server."
            ) from exc
        analyzer = SentimentIntensityAnalyzer()
        analyzer.lexicon.update({token: score for token, score in EMOJI_SENTIMENT.values()})
        analyzer.lexicon.update(SLANG_SENTIMENT)
        _analyzer = analyzer
    return _analyzer


def prepare_text(text: str) -> str:
    """Swap known emoji for controlled tokens before VADER's own emoji pass."""
    cleaned = text.replace(_VARIATION_SELECTOR, "")
    for emoji, (token, _score) in EMOJI_SENTIMENT.items():
        if emoji in cleaned:
            cleaned = cleaned.replace(emoji, f" {token} ")
    return re.sub(r"\s+", " ", cleaned).strip()


def classify(compound: float) -> str:
    if compound >= POSITIVE_THRESHOLD:
        return "positive"
    if compound <= NEGATIVE_THRESHOLD:
        return "negative"
    return "neutral"


def score_text(text: str) -> dict[str, Any]:
    prepared = prepare_text(text or "")
    if not prepared:
        return {"compound": 0.0, "label": "neutral", "positive": 0.0, "neutral": 1.0, "negative": 0.0}
    scores = _get_analyzer().polarity_scores(prepared)
    compound = round(float(scores["compound"]), 4)
    return {
        "compound": compound,
        "label": classify(compound),
        "positive": round(float(scores["pos"]), 4),
        "neutral": round(float(scores["neu"]), 4),
        "negative": round(float(scores["neg"]), 4),
    }


def score_comments(comments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    scored = []
    for comment in comments:
        result = score_text(comment.get("text", ""))
        scored.append({**comment, "sentiment": result["label"], "sentiment_score": result["compound"]})
    return scored


def summarize(scored: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate scored comments into a distribution and a net sentiment score."""
    total = len(scored)
    if not total:
        return {
            "comments_analyzed": 0,
            "distribution": {"positive": 0, "neutral": 0, "negative": 0},
            "distribution_percent": {"positive": 0.0, "neutral": 0.0, "negative": 0.0},
            "average_compound": 0.0,
            "net_sentiment_score": 0.0,
            "overall_label": "neutral",
        }

    counts = {"positive": 0, "neutral": 0, "negative": 0}
    for comment in scored:
        counts[comment["sentiment"]] += 1
    percents = {key: round(value / total * 100, 1) for key, value in counts.items()}
    average = round(sum(c["sentiment_score"] for c in scored) / total, 4)
    net = round(percents["positive"] - percents["negative"], 1)
    return {
        "comments_analyzed": total,
        "distribution": counts,
        "distribution_percent": percents,
        "average_compound": average,
        # Net sentiment is the positive share minus the negative share, so it
        # ignores the neutral mass that dominates emoji-only comment threads.
        "net_sentiment_score": net,
        "overall_label": classify(average),
    }


def extremes(scored: list[dict[str, Any]], limit: int = 3) -> dict[str, list[dict[str, Any]]]:
    positives = [c for c in scored if c["sentiment"] == "positive"]
    negatives = [c for c in scored if c["sentiment"] == "negative"]
    positives.sort(key=lambda c: (c["sentiment_score"], int(c.get("likes") or 0)), reverse=True)
    negatives.sort(key=lambda c: (-c["sentiment_score"], int(c.get("likes") or 0)), reverse=True)
    return {"most_positive": positives[:limit], "most_negative": negatives[:limit]}


def truncate(text: str, max_length: int = 60) -> str:
    cleaned = re.sub(r"\s+", " ", text or "").strip()
    if not cleaned:
        return "(empty)"
    if len(cleaned) > max_length:
        return cleaned[: max_length - 3].rstrip() + "..."
    return cleaned


def looks_non_latin(text: str) -> bool:
    """True when a comment's letters are mostly outside the Latin alphabet.

    The lexicon is English-only, so such comments score neutral regardless of
    what they actually say. Emoji-only comments are not counted here because the
    overlay scores those correctly.
    """
    letters = [char for char in text if char.isalpha()]
    if not letters:
        return False
    latin = sum(1 for char in letters if char.isascii())
    return latin / len(letters) < 0.5


def build_caveats(scored: list[dict[str, Any]]) -> list[str]:
    caveats = [
        "Scoring is English-only (VADER lexicon plus an emoji and social-slang overlay); "
        "it does not detect sarcasm."
    ]
    non_latin = sum(1 for comment in scored if looks_non_latin(comment.get("text", "")))
    if non_latin:
        share = round(non_latin / len(scored) * 100, 1)
        caveats.append(
            f"**{non_latin} of {len(scored)} comments ({share}%) are mostly non-Latin script** and were "
            "scored neutral by default, so the neutral share is inflated and this reading understates "
            "real sentiment for a multilingual audience."
        )
    return caveats


def build_distribution_table(summary: dict[str, Any]) -> str:
    counts = summary["distribution"]
    percents = summary["distribution_percent"]
    lines = [
        "| Sentiment | Comments | Share |",
        "|---|---|---|",
    ]
    for label in ("positive", "neutral", "negative"):
        lines.append(f"| {label.title()} | {counts[label]:,} | {percents[label]}% |")
    return "\n".join(lines)


def build_comment_table(scored: list[dict[str, Any]], limit: int = 10) -> str:
    lines = [
        "| Sentiment | Score | Likes | Comment |",
        "|---|---|---|---|",
    ]
    for comment in scored[:limit]:
        lines.append(
            f"| {comment['sentiment'].title()} | {comment['sentiment_score']:+.2f} | "
            f"{int(comment.get('likes') or 0):,} | {truncate(comment.get('text', ''))} |"
        )
    return "\n".join(lines)


def build_per_item_table(per_item: list[dict[str, Any]], caption_noun: str) -> str:
    lines = [
        f"| # | {caption_noun} | Comments | Pos | Neu | Neg | Net | Avg |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for index, row in enumerate(per_item, start=1):
        percents = row["distribution_percent"]
        lines.append(
            f"| {index} | {truncate(row['caption'], 40)} | {row['comments_analyzed']:,} | "
            f"{percents['positive']}% | {percents['neutral']}% | {percents['negative']}% | "
            f"{row['net_sentiment_score']:+.1f} | {row['average_compound']:+.2f} |"
        )
    return "\n".join(lines)


def generate_sentiment_insights(
    username: str,
    summary: dict[str, Any],
    highlights: dict[str, list[dict[str, Any]]],
    per_item: list[dict[str, Any]],
    item_noun: str,
) -> dict[str, Any]:
    percents = summary["distribution_percent"]
    net = summary["net_sentiment_score"]
    if net >= 40:
        verdict = "overwhelmingly positive"
    elif net >= 15:
        verdict = "positive"
    elif net > -15:
        verdict = "mixed or neutral"
    elif net > -40:
        verdict = "negative"
    else:
        verdict = "overwhelmingly negative"

    takeaways = [
        f"**Overall Reception:** Audience response to @{username} is **{verdict}** "
        f"(net sentiment **{net:+.1f}**, {percents['positive']}% positive vs {percents['negative']}% negative "
        f"across {summary['comments_analyzed']:,} comments).",
        f"**Neutral Share:** **{percents['neutral']}%** of comments carry no clear sentiment signal — "
        "typically tags, emoji without valence, or short replies.",
    ]

    if highlights["most_positive"]:
        top = highlights["most_positive"][0]
        takeaways.append(
            f"**Strongest Praise:** \"{truncate(top.get('text', ''), 70)}\" (score {top['sentiment_score']:+.2f})."
        )
    if highlights["most_negative"]:
        worst = highlights["most_negative"][0]
        takeaways.append(
            f"**Strongest Criticism:** \"{truncate(worst.get('text', ''), 70)}\" (score {worst['sentiment_score']:+.2f})."
        )

    recommendations = []
    if per_item:
        best = max(per_item, key=lambda row: row["net_sentiment_score"])
        worst = min(per_item, key=lambda row: row["net_sentiment_score"])
        recommendations.append(
            f"'{truncate(best['caption'], 45)}' drew the warmest response "
            f"(net {best['net_sentiment_score']:+.1f}) — study what that {item_noun} did differently."
        )
        if worst["net_sentiment_score"] < best["net_sentiment_score"]:
            recommendations.append(
                f"'{truncate(worst['caption'], 45)}' drew the coolest response "
                f"(net {worst['net_sentiment_score']:+.1f}) — review the comments there before repeating that format."
            )
    if percents["negative"] >= 20:
        recommendations.append(
            "Negative comments exceed one in five; triage the criticism themes before the next campaign brief."
        )
    else:
        recommendations.append(
            "Reply to the strongest praise to convert enthusiastic commenters into repeat advocates."
        )

    return {
        "key_takeaways": takeaways,
        "recommendations": recommendations,
        "verdict": verdict,
    }
