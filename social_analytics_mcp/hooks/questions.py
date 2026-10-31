"""Every question, level, weight, and threshold the caption hook evaluator sends or applies.

This is the module to audit and edit. Each question asks Jev for one judgment about a caption;
the decision of how good the hook is lives in `scoring.py`, which combines these answers in code.
"""

from __future__ import annotations

from typing import Any

from typesafe_sdk import Noul, Score


# A Noul above YES reads as yes, below NO as no, and anything between is "unclear".
YES = 0.7
NO = 0.3

# A Score is flagged as split when two levels at least two steps apart each hold this much
# probability: the position then sits in the middle while the model is torn between the ends.
SPLIT_MASS = 0.3

# Relative weight of each dimension in the composite. Renormalised over the dimensions that
# have a settled value, so an "unclear" Noul drops out rather than counting as zero.
DEFAULT_WEIGHTS: dict[str, float] = {
    "hook_strength": 0.35,
    "emotional_pull": 0.20,
    "relatability": 0.15,
    "audience_question": 0.15,
    "call_to_action": 0.15,
}


def build_state(caption: str) -> dict[str, str]:
    """What a person reviewing the post would look at: the whole caption and its first line.

    Feeds show only the first line before "more", so it is stated separately rather than leaving
    the model to find where the caption is cut.
    """
    opening_line = next((line.strip() for line in caption.splitlines() if line.strip()), caption.strip())
    return {"caption": caption, "opening_line": opening_line}


QUESTIONS: dict[str, Any] = {
    "hook_strength": Score(
        instructions=(
            "How strongly does `opening_line` make someone scrolling a social media feed "
            "want to read the rest of `caption`?"
        ),
        criteria=[
            "The opening line is filler, such as a greeting, a date, an emoji string, or only hashtags.",
            "The opening line states the topic plainly and gives no reason to keep reading.",
            "The opening line raises some interest, such as a mild claim, a teaser, or a relatable remark.",
            "The opening line creates strong curiosity, tension, or surprise that makes a reader want the rest.",
        ],
    ),
    "emotional_pull": Score(
        instructions="How strong an emotional reaction is `caption` likely to provoke in the people who read it?",
        criteria=[
            "The caption is purely informational, such as a product spec, a schedule, or a list of credits.",
            "The caption may raise mild interest or a smile.",
            "The caption evokes a clear emotion, such as excitement, nostalgia, humour, or pride.",
            "The caption evokes an intense emotion, such as awe, heartbreak, outrage, or deep gratitude.",
        ],
    ),
    "relatability": Score(
        instructions="How easily could a typical follower see their own life or experience in `caption`?",
        criteria=[
            "The caption is about something only the creator or brand experiences, such as a launch announcement.",
            "The caption touches on a common experience in passing.",
            "The caption centres on an experience many followers have had themselves.",
        ],
    ),
    "audience_question": Noul(
        instructions="Does `caption` ask its readers a question they could answer in the comments?",
        criteria={
            "true": "The caption asks readers something, such as their opinion, favourite, or experience.",
            "false": (
                "The caption asks no question, or only a rhetorical question that the caption answers itself."
            ),
        },
    ),
    "has_call_to_action": Noul(
        instructions=(
            "Does `caption` tell its readers to take an action, such as commenting, sharing, saving, "
            "following, tagging a friend, or visiting a link?"
        ),
        criteria={
            "true": "The caption tells the reader to do something, such as 'tag a friend' or 'link in bio'.",
            "false": "The caption describes or shares something and never tells the reader to do anything.",
        },
    ),
    # Asked speculatively: scoring.py reads it only when has_call_to_action is a yes.
    "cta_specificity": Score(
        instructions="How specific is the action that `caption` tells its readers to take?",
        criteria=[
            "A vague nudge, such as 'let me know' or 'check it out'.",
            "A named action, such as 'comment below', 'save this', or 'link in bio'.",
            "A named action with exactly what to do, such as 'comment your favourite city' or 'tag a friend who needs this'.",
        ],
    ),
}
