"""
Reads the chat's request, never trusting it (ADR-0004's amendment on the wrapper's whole input; the chat's contract):
a run carries a new message, a resume, or neither (the warm-up), and the entrypoint builds the wrapper's input from that
alone. A request that fails the contract, or the checks the contract can't express, is refused with each failure's
path and rule, never its value (POL-11). Until the controls land, no control is ever pending, so every resume is refused.
"""

from collections.abc import Collection
from dataclasses import dataclass
from typing import Any

from banking_agent.contracts import validator
from banking_agent.masking import mask
from banking_agent.tools import MAX_ERRORS, pointer


@dataclass(frozen=True)
class NewMessage:
    id: str
    text: str


@dataclass(frozen=True)
class Warmup:
    pass


class RequestRefusedError(Exception):
    def __init__(self, errors: list[dict[str, str]]) -> None:
        super().__init__("invalid_request")
        self.errors = errors[:MAX_ERRORS]


def errors_of(definition: str, instance: Any, prefix: str = "") -> list[dict[str, str]]:
    found: list[dict[str, str]] = []
    for error in validator("chat", definition).iter_errors(instance):
        entry = {"path": f"{prefix}{pointer(error)}", "rule": str(error.validator)}
        if entry not in found:
            found.append(entry)
    return sorted(found, key=lambda e: (e["path"], e["rule"]))


def check_contract(request: dict[str, Any]) -> None:
    errors = errors_of("request", request)
    if errors:
        raise RequestRefusedError(errors)


def refused(path: str, rule: str) -> RequestRefusedError:
    return RequestRefusedError([{"path": path, "rule": rule}])


def read(request: dict[str, Any], held: Collection[str]) -> NewMessage | Warmup:
    """
    request has passed check_contract; held is the message IDs the thread's checkpoint holds.
    """
    warmup = (request.get("forwardedProps") or {}).get("warmup") is True
    resume = bool(request.get("resume"))
    messages = request["messages"]
    last = len(messages) - 1
    new: dict[str, Any] | None = None
    if messages:
        message_errors = errors_of("user_message", messages[last], f"/messages/{last}")
        if not message_errors and messages[last]["id"] not in held:
            new = messages[last]
        elif not warmup and not resume:
            raise RequestRefusedError(
                message_errors or [{"path": f"/messages/{last}/id", "rule": "notNew"}]
            )
    if warmup and (new is not None or resume):
        raise refused("/forwardedProps/warmup", "conflict")
    if resume and new is not None:
        raise refused("/resume", "conflict")
    if resume:
        raise refused("/resume", "notPending")
    if warmup:
        return Warmup()
    if new is None:
        raise refused("/messages", "notNew")
    text = mask(new["content"])
    if not text.strip():
        raise refused(f"/messages/{last}/content", "minLength")
    return NewMessage(new["id"], text)
