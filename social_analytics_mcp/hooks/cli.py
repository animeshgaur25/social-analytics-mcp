"""Score social post captions on engagement-hook dimensions with TypeSafe's Jev.

    caption-hooks captions.txt
    caption-hooks posts.jsonl --json
    caption-hooks posts.csv --dry-run
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TextIO

from dotenv import load_dotenv
from typesafe_sdk import AsyncTypeSafeClient, TypeSafeError
from typesafe_sdk.constants import DEFAULT_MODEL, DEFAULT_MODEL_ENV

from .questions import DEFAULT_WEIGHTS, QUESTIONS, build_state
from .scoring import Evaluation, evaluate, noul_verdict, parse_weights


COLUMNS = {
    "hook_strength": "hook",
    "emotional_pull": "emotion",
    "relatability": "relate",
    "audience_question": "asks?",
    "call_to_action": "cta",
}


@dataclass
class Caption:
    id: str
    text: str


@dataclass
class Result:
    caption: Caption
    request: dict[str, Any]
    answers: dict[str, Any] | None = None
    evaluation: Evaluation | None = None
    error: str | None = None


def read_captions(path: str) -> list[Caption]:
    """Read .txt (one caption per line), .jsonl (strings or {"id", "text"}), or .csv (a text column)."""
    if path == "-":
        return _from_lines(sys.stdin)
    file = Path(path)
    with file.open(encoding="utf-8", newline="") as handle:
        suffix = file.suffix.lower()
        if suffix == ".jsonl":
            return _from_jsonl(handle)
        if suffix == ".csv":
            return _from_csv(handle)
        return _from_lines(handle)


def _from_lines(handle: TextIO) -> list[Caption]:
    lines = (line.strip() for line in handle)
    return [Caption(str(i), line) for i, line in enumerate(filter(None, lines), start=1)]


def _from_jsonl(handle: TextIO) -> list[Caption]:
    captions = []
    for number, line in enumerate(handle, start=1):
        if not line.strip():
            continue
        record = json.loads(line)
        if isinstance(record, str):
            record = {"text": record}
        text = record.get("text") or record.get("caption")
        if not isinstance(text, str) or not text.strip():
            raise ValueError(f"Line {number} has no 'text' (or 'caption') string.")
        captions.append(Caption(str(record.get("id", len(captions) + 1)), text))
    return captions


def _from_csv(handle: TextIO) -> list[Caption]:
    reader = csv.DictReader(handle)
    column = next((name for name in ("text", "caption") if name in (reader.fieldnames or [])), None)
    if column is None:
        raise ValueError("CSV needs a 'text' or 'caption' column.")
    captions = []
    for row in reader:
        text = (row.get(column) or "").strip()
        if text:
            captions.append(Caption(row.get("id") or str(len(captions) + 1), text))
    return captions


def request_payload(caption: Caption, model: str | None) -> dict[str, Any]:
    """The exact body sent for one caption; printed by --dry-run and kept in --json output."""
    return {
        "model": model or os.environ.get(DEFAULT_MODEL_ENV) or DEFAULT_MODEL,
        "state": build_state(caption.text),
        "questions": {name: question.model_dump(mode="json", exclude_none=True) for name, question in QUESTIONS.items()},
    }


async def score_all(
    captions: list[Caption],
    *,
    model: str | None,
    weights: dict[str, float],
    concurrency: int,
    transport: Any = None,
) -> list[Result]:
    limit = asyncio.Semaphore(concurrency)
    async with AsyncTypeSafeClient(model=model, transport=transport) as client:

        async def one(caption: Caption) -> Result:
            result = Result(caption, request_payload(caption, model))
            async with limit:
                try:
                    response = await client.system_one(state=result.request["state"], questions=QUESTIONS)
                except TypeSafeError as exc:
                    # A failed call is an error row, never a low score.
                    result.error = f"{type(exc).__name__}: {exc}"
                    return result
            result.answers = response.answers
            result.evaluation = evaluate(response.answers, weights)
            return result

        return await asyncio.gather(*(one(caption) for caption in captions))


def _cell(name: str, value: float | None, split: list[str]) -> str:
    if value is None:
        return "?"
    if name == "audience_question":
        return "yes" if value else "no"
    return f"{value * 100:.0f}{'~' if name in split else ''}"


def render_table(results: list[Result]) -> str:
    headers = ["id", *COLUMNS.values(), "score", "caption"]
    rows = []
    for result in results:
        preview = " ".join(result.caption.text.split())
        preview = preview if len(preview) <= 48 else preview[:47] + "…"
        if result.error:
            rows.append([result.caption.id, *(["-"] * len(COLUMNS)), "ERROR", result.error])
            continue
        evaluation = result.evaluation
        assert evaluation is not None
        cells = [_cell(name, evaluation.dimensions[name], evaluation.split) for name in COLUMNS]
        composite = "?" if evaluation.composite is None else f"{evaluation.composite:.1f}"
        rows.append([result.caption.id, *cells, composite, preview])

    widths = [max(len(str(row[i])) for row in [headers, *rows]) for i in range(len(headers))]
    lines = ["  ".join(str(cell).ljust(width) for cell, width in zip(row, widths)).rstrip() for row in [headers, *rows]]
    lines.insert(1, "  ".join("-" * width for width in widths))
    lines.append("")
    lines.append("Dimensions are 0-100. '?' = Jev's answer was between the yes/no thresholds, so it is left out of")
    lines.append("the score. '~' = Jev was split between distant levels; read the --json probabilities.")
    return "\n".join(lines)


def to_json(results: list[Result]) -> list[dict[str, Any]]:
    out = []
    for result in results:
        record: dict[str, Any] = {"id": result.caption.id, "text": result.caption.text, "request": result.request}
        if result.error:
            record["error"] = result.error
        else:
            assert result.evaluation is not None and result.answers is not None
            record["composite"] = result.evaluation.composite
            record["dimensions"] = result.evaluation.dimensions
            record["split"] = result.evaluation.split
            record["answers"] = {name: answer.model_dump(mode="json") for name, answer in result.answers.items()}
            record["verdicts"] = {
                name: noul_verdict(answer.noul) for name, answer in result.answers.items() if hasattr(answer, "noul")
            }
        out.append(record)
    return out


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="caption-hooks",
        description="Score social post captions on engagement-hook dimensions with TypeSafe's Jev.",
    )
    parser.add_argument("input", help="A .txt (one caption per line), .jsonl, or .csv file, or '-' for stdin lines.")
    parser.add_argument("--json", action="store_true", help="Print full results, answers, and request payloads as JSON.")
    parser.add_argument("--dry-run", action="store_true", help="Print the request payloads without calling the API.")
    parser.add_argument("--model", default=None, help="System One model (default: jev-latest or TYPESAFE_DEFAULT_MODEL).")
    parser.add_argument(
        "--weights",
        default="",
        help=f"Override composite weights, e.g. 'hook_strength=0.5'. Dimensions: {', '.join(DEFAULT_WEIGHTS)}.",
    )
    parser.add_argument("--concurrency", type=int, default=4, help="Captions scored at once (default 4).")
    parser.add_argument("--sort", action="store_true", help="Sort by composite score, highest first.")
    return parser


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        weights = parse_weights(args.weights)
        captions = read_captions(args.input)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    if not captions:
        parser.error("No captions found in the input.")
    if args.concurrency < 1:
        parser.error("--concurrency must be at least 1.")

    if args.dry_run:
        print(json.dumps([request_payload(caption, args.model) for caption in captions], indent=2, ensure_ascii=False))
        return 0

    try:
        results = asyncio.run(score_all(captions, model=args.model, weights=weights, concurrency=args.concurrency))
    except TypeSafeError as exc:  # e.g. a missing or malformed API key, raised before any request
        print(f"caption-hooks: {exc}", file=sys.stderr)
        return 2
    if args.sort:
        results.sort(key=lambda r: -1 if r.evaluation is None or r.evaluation.composite is None else r.evaluation.composite, reverse=True)

    print(json.dumps(to_json(results), indent=2, ensure_ascii=False) if args.json else render_table(results))
    return 1 if any(result.error for result in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
