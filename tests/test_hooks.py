"""Offline checks for the caption-hooks CLI: input parsing, scoring logic, and the request it sends.

The TypeSafe API is replaced by a mock transport, so no key or network access is needed.
"""

from __future__ import annotations

import asyncio
import io
import json
import os
from contextlib import redirect_stdout
from pathlib import Path
import sys
import tempfile

import httpx2

from social_analytics_mcp.hooks.cli import Caption, main, read_captions, render_table, score_all
from social_analytics_mcp.hooks.questions import DEFAULT_WEIGHTS, QUESTIONS
from social_analytics_mcp.hooks.scoring import evaluate, is_split, noul_verdict, parse_weights
from typesafe_sdk import RetryPolicy


def score_answer(probabilities: list[float]) -> dict:
    return {
        "type": "score",
        "score": sum(level * p for level, p in enumerate(probabilities)),
        "confidence": max(probabilities),
        "legend": {str(level): f"level {level}" for level in range(len(probabilities))},
        "probabilities": {str(level): p for level, p in enumerate(probabilities)},
    }


def noul_answer(probability: float) -> dict:
    return {"type": "noul", "noul": probability}


STRONG = {
    "hook_strength": score_answer([0, 0, 0, 1]),
    "emotional_pull": score_answer([0, 0, 0, 1]),
    "relatability": score_answer([0, 0, 1]),
    "audience_question": noul_answer(0.95),
    "has_call_to_action": noul_answer(0.9),
    "cta_specificity": score_answer([0, 0, 1]),
}

WEAK = {
    "hook_strength": score_answer([1, 0, 0, 0]),
    "emotional_pull": score_answer([1, 0, 0, 0]),
    "relatability": score_answer([1, 0, 0]),
    "audience_question": noul_answer(0.05),
    "has_call_to_action": noul_answer(0.1),
    # Speculative answer that scoring must ignore because there is no call to action.
    "cta_specificity": score_answer([0, 0, 1]),
}


def parsed(answers: dict) -> dict:
    """Run raw answer JSON through the SDK's own response model, as the client does."""
    from typesafe_sdk import SystemOneResponse

    return SystemOneResponse.model_validate_json(json.dumps({"model": "jev-1.14.0", "answers": answers, "usage": {}})).answers


def verify_scoring() -> None:
    strong = evaluate(parsed(STRONG))
    assert strong.composite == 100.0, strong
    weak = evaluate(parsed(WEAK))
    assert weak.composite == 0.0, weak
    assert weak.dimensions["call_to_action"] == 0.0

    # An unsettled Noul drops out of the composite instead of counting as a no.
    unclear = evaluate(parsed({**STRONG, "audience_question": noul_answer(0.5), "has_call_to_action": noul_answer(0.5)}))
    assert unclear.dimensions["audience_question"] is None
    assert unclear.dimensions["call_to_action"] is None
    assert unclear.composite == 100.0

    # A vague CTA still earns half the dimension for being present.
    vague = evaluate(parsed({**STRONG, "cta_specificity": score_answer([1, 0, 0])}))
    assert vague.dimensions["call_to_action"] == 0.5

    split = evaluate(parsed({**STRONG, "hook_strength": score_answer([0.5, 0, 0, 0.5])}))
    assert split.split == ["hook_strength"]
    assert not is_split({0: 0.4, 1: 0.6})

    assert noul_verdict(0.7) is True and noul_verdict(0.3) is False and noul_verdict(0.5) is None

    weights = parse_weights("hook_strength=1, relatability=0")
    assert weights["hook_strength"] == 1 and weights["relatability"] == 0
    assert weights["emotional_pull"] == DEFAULT_WEIGHTS["emotional_pull"]
    for bad in ("nope=1", "hook_strength=x", "hook_strength=-1"):
        try:
            parse_weights(bad)
        except ValueError:
            continue
        raise AssertionError(f"parse_weights accepted {bad!r}")


def verify_input_formats() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "a.txt").write_text("first caption\n\nsecond caption\n", encoding="utf-8")
        (root / "a.jsonl").write_text(
            '"plain string"\n{"id": "x", "text": "line one\\nline two"}\n{"caption": "alt key"}\n', encoding="utf-8"
        )
        (root / "a.csv").write_text('id,caption\np1,"multi\nline"\np2,\n,no id\n', encoding="utf-8")

        assert [c.text for c in read_captions(str(root / "a.txt"))] == ["first caption", "second caption"]
        jsonl = read_captions(str(root / "a.jsonl"))
        assert [(c.id, c.text) for c in jsonl] == [("1", "plain string"), ("x", "line one\nline two"), ("3", "alt key")]
        csv_rows = read_captions(str(root / "a.csv"))
        assert [(c.id, c.text) for c in csv_rows] == [("p1", "multi\nline"), ("2", "no id")]


def verify_requests_and_errors() -> None:
    sent: list[dict] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        body = json.loads(request.content)
        sent.append(body)
        if "boom" in body["state"]["caption"]:
            return httpx2.Response(500, json={"error": {"message": "server exploded"}})
        answers = STRONG if "strong" in body["state"]["caption"] else WEAK
        return httpx2.Response(200, json={"model": "jev-1.14.0", "answers": answers, "usage": {}})

    os.environ.setdefault("TYPESAFE_API_KEY", "test-key-offline")
    captions = [Caption("1", "strong opener\nsecond line"), Caption("2", "weak"), Caption("3", "boom")]
    from social_analytics_mcp.hooks import cli

    original = cli.AsyncTypeSafeClient
    cli.AsyncTypeSafeClient = lambda **kw: original(**kw, retry=RetryPolicy(max_retries=0), compression=False)  # type: ignore[assignment]
    try:
        results = asyncio.run(
            score_all(
                captions, model=None, weights=DEFAULT_WEIGHTS, concurrency=2, transport=httpx2.MockTransport(handler)
            )
        )
    finally:
        cli.AsyncTypeSafeClient = original  # type: ignore[assignment]

    # One request per caption carries every question and the state built in code.
    assert len(sent) == 3
    first = next(body for body in sent if body["state"]["caption"].startswith("strong"))
    assert first["state"] == {"caption": "strong opener\nsecond line", "opening_line": "strong opener"}
    assert set(first["questions"]) == set(QUESTIONS)

    by_id = {result.caption.id: result for result in results}
    assert by_id["1"].evaluation.composite == 100.0
    assert by_id["2"].evaluation.composite == 0.0
    # A failed call is reported as an error, never scored as a weak caption.
    assert by_id["3"].evaluation is None and by_id["3"].error

    table = render_table(results)
    assert "ERROR" in table and "100.0" in table


def verify_dry_run() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "c.txt"
        path.write_text("hello world\n", encoding="utf-8")
        out = io.StringIO()
        with redirect_stdout(out):
            code = main([str(path), "--dry-run"])
    payloads = json.loads(out.getvalue())
    assert code == 0 and len(payloads) == 1
    assert payloads[0]["questions"]["has_call_to_action"]["type"] == "noul"


if __name__ == "__main__":
    for check in (verify_scoring, verify_input_formats, verify_requests_and_errors, verify_dry_run):
        check()
        print(f"ok  {check.__name__}")
    sys.exit(0)
