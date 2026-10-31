"""Turns Jev's answers about one caption into dimension values and a 0-100 composite."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .questions import DEFAULT_WEIGHTS, NO, SPLIT_MASS, YES


@dataclass
class Evaluation:
    """Each dimension normalised to 0-1, or None when its answer did not settle it."""

    dimensions: dict[str, float | None]
    composite: float | None
    split: list[str] = field(default_factory=list)


def noul_verdict(probability: float) -> bool | None:
    """Yes above YES, no below NO, None for the unsettled band between."""
    if probability >= YES:
        return True
    if probability <= NO:
        return False
    return None


def is_split(probabilities: dict[int, float]) -> bool:
    """True when two levels at least two steps apart each carry SPLIT_MASS or more."""
    heavy = [level for level, p in probabilities.items() if p >= SPLIT_MASS]
    return bool(heavy) and max(heavy) - min(heavy) >= 2


def _score_fraction(answer: Any) -> float:
    top = max(answer.legend) if answer.legend else max(answer.probabilities)
    return answer.score / top if top else 0.0


def evaluate(answers: dict[str, Any], weights: dict[str, float] | None = None) -> Evaluation:
    weights = weights or DEFAULT_WEIGHTS
    dimensions: dict[str, float | None] = {}
    split: list[str] = []

    for name in ("hook_strength", "emotional_pull", "relatability"):
        dimensions[name] = _score_fraction(answers[name])
        if is_split(answers[name].probabilities):
            split.append(name)

    question = noul_verdict(answers["audience_question"].noul)
    dimensions["audience_question"] = None if question is None else float(question)

    # Truth table for the call to action:
    #   has CTA yes     -> 0.5 for having one, plus up to 0.5 for how specific it is
    #   has CTA no      -> 0
    #   has CTA unclear -> None (left out of the composite and shown as "?")
    has_cta = noul_verdict(answers["has_call_to_action"].noul)
    if has_cta is True:
        dimensions["call_to_action"] = 0.5 + 0.5 * _score_fraction(answers["cta_specificity"])
        if is_split(answers["cta_specificity"].probabilities):
            split.append("call_to_action")
    elif has_cta is False:
        dimensions["call_to_action"] = 0.0
    else:
        dimensions["call_to_action"] = None

    settled = {name: value for name, value in dimensions.items() if value is not None and weights.get(name, 0) > 0}
    total_weight = sum(weights[name] for name in settled)
    composite = (
        round(100 * sum(weights[name] * value for name, value in settled.items()) / total_weight, 1)
        if total_weight
        else None
    )
    return Evaluation(dimensions=dimensions, composite=composite, split=split)


def parse_weights(spec: str) -> dict[str, float]:
    """Parse 'hook_strength=0.5,call_to_action=0.2'; unnamed dimensions keep their defaults."""
    weights = dict(DEFAULT_WEIGHTS)
    for part in filter(None, (piece.strip() for piece in spec.split(","))):
        name, _, value = part.partition("=")
        name = name.strip()
        if name not in DEFAULT_WEIGHTS:
            raise ValueError(f"Unknown dimension '{name}'. Choose from: {', '.join(DEFAULT_WEIGHTS)}.")
        try:
            weights[name] = float(value)
        except ValueError:
            raise ValueError(f"Weight for '{name}' must be a number, got '{value}'.") from None
        if weights[name] < 0:
            raise ValueError(f"Weight for '{name}' must not be negative.")
    return weights
