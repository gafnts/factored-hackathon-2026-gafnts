"""
The commands that call models outside the system under test, which __main__ adds to its own. judge has Claude Opus
5.5 grade a run's replies, or a sample's, through the batch API, keeping its items, attempts, judgments, and manifest
under data/evaluation/judge/. With --estimate a command prices its calls and makes none; otherwise it reads the
Anthropic key from the env file, as the live language check does, and sends it to the client only. Each prints
counts, never a reply, a value, or the key (SEC-03).
"""

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import anthropic

from banking_agent.evaluation import judge, rubric, runs
from banking_agent.model_key import ModelKeyError, read_key

COMMANDS = ("judge",)


def add(commands: Any) -> None:
    judging = commands.add_parser(
        "judge",
        help="Have the judge grade a run's replies, or a sample's, through the batch API",
    )
    source = judging.add_mutually_exclusive_group(required=True)
    source.add_argument("--run", type=Path, help="A run under data/evaluation/runs/")
    source.add_argument(
        "--items", type=Path, help="Items to judge, as a sample keeps them"
    )
    judging.add_argument("--env-file", type=Path, default=Path(".env"))
    judging.add_argument("--out", type=Path, default=judge.OUT)
    judging.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Judge this many, each question covered first",
    )
    judging.add_argument(
        "--estimate", action="store_true", help="Price it without calling the model"
    )


def run_judge(args: argparse.Namespace, code: dict[str, Any]) -> None:
    loaded = rubric.load()
    found = judge.run_items(args.run) if args.run else judge.read_items(args.items)
    if args.limit is not None:
        found = judge.chosen(found, loaded, args.limit)
    if args.estimate:
        priced = judge.estimate(found, loaded)
        print(
            f"{priced['items']} replies: about {priced['input_tokens']} input and {priced['output_tokens']} "
            f"output tokens, about {priced['cost_usd']:.2f} USD at the batch's list price of {priced['priced_on']}"
        )
        return
    client = anthropic.Anthropic(api_key=read_key(args.env_file))
    started = datetime.now(UTC)
    judged = judge.judge(found, loaded, judge.AnthropicBatches(client))
    out = args.out / runs.run_id()
    manifest = judge.keep(
        out,
        found,
        loaded,
        judged,
        judge.source(args.run, args.items, found),
        code,
        (started, datetime.now(UTC)),
    )
    print(
        f"judged {manifest['items']} replies in {manifest['attempts']} attempts; outcomes {manifest['outcomes']}; "
        f"{manifest['by_hand']} judgments for a person; {manifest['totals']['cost_usd']:.4f} USD; kept in {out}"
    )


def main(args: argparse.Namespace, code: dict[str, Any]) -> int:
    try:
        if args.command == "judge":
            run_judge(args, code)
    except ModelKeyError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    return 0
