"""
A drawn set run end to end against a deployed stack (ADR-0005, Running a case; The run manifest): its cases played in
parallel by the harness, each graded from its stored evidence, and kept once as it finishes, so a run that stops keeps
what it played. Results go under data/evaluation/runs/<run>/, never committed, since they hold the cases' values
(SEC-03), and to the evaluation bucket under runs/<run>/ when the stack has one, by writes the bucket refuses without
If-None-Match, so nothing a grader read is ever rewritten. The run's manifest says what ran, against what, and how;
the summary holds counts, so it can be printed.
"""

import hashlib
import json
import statistics
import threading
from collections.abc import Callable, Iterable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import httpx

from banking_agent.evaluation import (
    cases,
    client,
    deployed,
    disagreements,
    generator,
    grader,
    harness,
    oracle,
    runs,
    users,
)

if TYPE_CHECKING:
    from mypy_boto3_s3 import S3Client

Played = tuple[dict[str, Any], dict[str, Any], dict[str, Any]]


class RunError(ValueError):
    pass


class Keeper:
    """
    A run's results, each written once.
    """

    def __init__(
        self, out: Path, run: str, s3: "S3Client | None", bucket: str | None
    ) -> None:
        self.out, self.run = out, run
        self.s3, self.bucket = s3, bucket
        self.hashes: dict[str, str] = {}
        self.lock = threading.Lock()

    def keep(self, name: str, data: Any) -> None:
        body = (json.dumps(data, ensure_ascii=False, sort_keys=True) + "\n").encode()
        path = self.out / name
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as kept:
            kept.write(body)
        if self.s3 is not None and self.bucket is not None:
            self.s3.put_object(
                Bucket=self.bucket,
                Key=f"runs/{self.run}/{name}",
                Body=body,
                ContentType="application/json",
                IfNoneMatch="*",
            )
        with self.lock:
            self.hashes[name] = hashlib.sha256(body).hexdigest()


def drawn(set_path: Path, manifest: Mapping[str, Any]) -> list[dict[str, Any]]:
    """
    The drawn set, refused unless it's the one its committed manifest describes.
    """
    found = list(cases.read(set_path))
    digest = hashlib.sha256(
        "".join(generator.digest(c) for c in found).encode()
    ).hexdigest()
    if digest != manifest["sha256"]:
        raise RunError("the drawn set isn't the one its manifest describes")
    if any(c["side"] != "development" for c in found):
        raise RunError("only development cases run before the held-out set is drawn")
    return found


def selected(
    found: Sequence[dict[str, Any]],
    situations: Iterable[str] = (),
    languages: Iterable[str] = (),
    limit: int | None = None,
) -> list[dict[str, Any]]:
    wanted, spoken = set(situations), set(languages)
    chosen = [
        c
        for c in found
        if (not wanted or c["situation"] in wanted)
        and (not spoken or c["language"] in spoken)
    ]
    return chosen[:limit]


def play_all(
    chosen: Sequence[dict[str, Any]],
    run: str,
    play: Callable[[dict[str, Any], str], dict[str, Any]],
    keeper: Keeper,
    parallel: int,
) -> list[Played]:
    def one(n: int, case: dict[str, Any]) -> Played:
        name = users.username(run, n)
        try:
            evidence = play(case, name)
        except Exception as error:
            # A stack that failed outside a turn (a test user, a table): the harness's error, never the agent's.
            evidence = {
                "case_id": case["case_id"],
                "customer_id": case["customer_id"],
                "mode": "end_to_end",
                "user": name,
                "turns": [],
                "record": [],
                "error": f"harness: {type(error).__name__}",
            }
        graded = grader.grade(case, evidence)
        keeper.keep(f"cases/{n:04d}.json", {"evidence": evidence, "grade": graded})
        return case, evidence, graded

    with ThreadPoolExecutor(max_workers=parallel) as pool:
        return list(pool.map(one, range(1, len(chosen) + 1), chosen))


def latency(played: Sequence[Played]) -> dict[str, Any]:
    """
    Each turn's latency, from the send to its last event, with each case's first turn apart, since each case opens a
    runtime session of its own (ADR-0005, Reporting). Fault cases are left out, since a planned failure answers at
    once (ADR-0005's amendment of 2026-10-01).
    """

    def spread(values: list[int]) -> dict[str, Any]:
        if len(values) < 2:
            return {"turns": len(values), "p50": values[0] if values else None}
        cuts = statistics.quantiles(values, n=20, method="inclusive")
        return {"turns": len(values), "p50": statistics.median(values), "p95": cuts[18]}

    first: list[int] = []
    later: list[int] = []
    faulted = [case for case, _, _ in played if case["faults"]]
    for case, evidence, _ in played:
        if case["faults"]:
            continue
        for n, turn in enumerate(evidence["turns"]):
            if turn["events"]:
                (later if n else first).append(turn["events"][-1]["at_ms"])
    return {
        "first": spread(first),
        "later": spread(later),
        "fault_cases_left_out": len(faulted),
    }


def summarize(played: Sequence[Played]) -> dict[str, Any]:
    return {
        **runs.summarize([(c, g) for c, _, g in played], disagreements.load()),
        "not_stopped": sum(e.get("session") == "not_stopped" for _, e, _ in played),
        "resent": sum(t.get("resent", 0) for _, e, _ in played for t in e["turns"]),
        "latency_ms": latency(played),
    }


def totals(played: Sequence[Played]) -> dict[str, Any]:
    """
    The turns' totals as the record closed them, the warmups' among them, which run no model.
    """
    closed = [
        e["totals"]
        for _, evidence, _ in played
        for e in evidence["record"]
        if e["kind"] == "turn_closed"
    ]
    costs = [t["cost_usd"] for t in closed]
    return {
        "turns": sum(len(grader.record_turns(e["record"])) for _, e, _ in played),
        **{
            k: sum(t[k] for t in closed)
            for k in ("model_calls", "tool_calls", "input_tokens", "output_tokens")
        },
        "cost_usd": None if None in costs else round(sum(costs), 6),
    }


def models(played: Sequence[Played]) -> list[dict[str, Any]]:
    """
    Per node and purpose, the model requested and the model_name returned, its settings and prompt, and its usage.
    """
    by: dict[tuple[str, ...], dict[str, Any]] = {}
    for _, evidence, _ in played:
        for e in evidence["record"]:
            if e["kind"] != "model_call":
                continue
            key = (e["node"], e["purpose"], e["provider"], e["model_requested"])
            seen = by.setdefault(
                key,
                {
                    "node": e["node"],
                    "purpose": e["purpose"],
                    "provider": e["provider"],
                    "model_requested": e["model_requested"],
                    "model_returned": set(),
                    "settings": set(),
                    "prompt_version": set(),
                    "calls": 0,
                    "usage": {},
                },
            )
            seen["calls"] += 1
            if e["model_returned"] is not None:
                seen["model_returned"].add(e["model_returned"])
            seen["settings"].add(json.dumps(e["settings"], sort_keys=True))
            seen["prompt_version"].add(e["prompt_version"])
            for k, v in (e["usage"] or {}).items():
                seen["usage"][k] = seen["usage"].get(k, 0) + (v or 0)
    return [
        {
            **m,
            "model_returned": sorted(m["model_returned"]),
            "settings": [json.loads(s) for s in sorted(m["settings"])],
            "prompt_version": sorted(m["prompt_version"]),
        }
        for _, m in sorted(by.items())
    ]


def digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True).encode()
    ).hexdigest()


def manifest(
    run: str,
    times: tuple[datetime, datetime],
    code: Mapping[str, Any],
    stack: deployed.Deployed,
    runs_as: str,
    set_manifest: Mapping[str, Any],
    chosen: Sequence[Mapping[str, Any]],
    selection: Mapping[str, Any],
    parallel: int,
    played: Sequence[Played],
    results: Mapping[str, str],
) -> dict[str, Any]:
    deployed_versions = {
        json.dumps(e["versions"], sort_keys=True)
        for _, evidence, _ in played
        for e in evidence["record"]
        if e["kind"] == "turn_opened"
    }
    return {
        "run": run,
        "mode": "end_to_end",
        "started_at": times[0].isoformat(),
        "ended_at": times[1].isoformat(),
        "code": dict(code),
        "stack": {
            "environment": stack.environment,
            "stamp": dict(stack.stamp),
            "clock": dict(stack.clock),
            "versions": [json.loads(v) for v in sorted(deployed_versions)],
            "runs_as": runs_as,
        },
        "set": {
            "name": set_manifest["set"],
            "seed": set_manifest["seed"],
            "versions": set_manifest["versions"],
            "sha256": set_manifest["sha256"],
            "selected": dict(selection),
            "cases": len(chosen),
        },
        "oracle": {"policy": oracle.POLICY_VERSION},
        "grader": grader.VERSION,
        "system": "deployed",
        "judge": None,
        "models": models(played),
        "fixtures": digest([c["fixtures"] for c in chosen]),
        "faults": digest([c["faults"] for c in chosen]),
        "parallelism": parallel,
        "repeats": 1,
        "pace": {"rate": client.RATE, "window_s": client.WINDOW},
        "totals": totals(played),
        "results": dict(sorted(results.items())),
    }


def connect(
    stack: deployed.Deployed, run: str
) -> tuple[users.Users, harness.Tables, "S3Client | None", str]:
    session, runs_as = deployed.session(stack, run)
    found = users.Users(
        session.client("cognito-idp"), stack.user_pool_id, stack.client_id
    )
    tables = harness.Tables(session.client("dynamodb"), stack)
    s3 = session.client("s3") if stack.bucket is not None else None
    return found, tables, s3, runs_as


def run(
    set_path: Path,
    set_manifest: Mapping[str, Any],
    stack_path: Path,
    out_dir: Path,
    code: Mapping[str, Any],
    selection: Mapping[str, Any],
    parallel: int,
) -> tuple[str, dict[str, Any]]:
    stack = deployed.read(stack_path)
    deployed.check(stack, set_manifest["versions"])
    chosen = selected(drawn(set_path, set_manifest), **selection)
    if not chosen:
        raise RunError("no case of the set matches the selection")
    run_id = runs.run_id()
    started = datetime.now(UTC)
    test_users, tables, s3, runs_as = connect(stack, run_id)
    keeper = Keeper(out_dir / run_id, run_id, s3, stack.bucket)
    with httpx.Client(timeout=client.TIMEOUT) as http:
        agui = client.Client(stack.invoke_url, stack.stop_url, http)
        gateway = client.Gateway(stack.gateway_url, stack.gateway_targets, http)

        def play(case: dict[str, Any], name: str) -> dict[str, Any]:
            if case["situation"].startswith("access."):
                return harness.play_access(case, name, test_users, gateway, tables)
            return harness.play(case, name, test_users, agui, tables)

        try:
            played = play_all(chosen, run_id, play, keeper, parallel)
        finally:
            test_users.cleanup(run_id)
    summary = {"run": run_id, "set": set_manifest["set"], **summarize(played)}
    keeper.keep("summary.json", summary)
    keeper.keep(
        "manifest.json",
        manifest(
            run_id,
            (started, datetime.now(UTC)),
            code,
            stack,
            runs_as,
            set_manifest,
            chosen,
            selection,
            parallel,
            played,
            keeper.hashes,
        ),
    )
    return run_id, summary


def cleanup(stack_path: Path, run: str | None) -> int:
    stack = deployed.read(stack_path)
    test_users, _, _, _ = connect(stack, run or "cleanup")
    return test_users.cleanup(run)
