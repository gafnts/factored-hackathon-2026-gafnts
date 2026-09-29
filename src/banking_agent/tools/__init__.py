"""
The card support tools (ADR-0004, decision 16): each validates its input against the full contract before it acts,
since the Gateway checks only a reduced copy, and answers an input that fails with each field's path and the rule it
broke, never its value, which may be a card number (POL-11).
"""

from typing import Any

from jsonschema import ValidationError

from banking_agent.contracts import validator

MAX_ERRORS = 20
MAX_PATH = 256


def pointer(error: ValidationError) -> str:
    parts = (str(p).replace("~", "~0").replace("/", "~1") for p in error.absolute_path)
    return "".join(f"/{part}" for part in parts)[:MAX_PATH]


def invalid_input(tool: str, arguments: Any) -> dict[str, Any] | None:
    errors: list[dict[str, str]] = []
    for error in validator("tools", f"{tool}_input").iter_errors(arguments):
        entry = {"path": pointer(error), "rule": str(error.validator)}
        if entry not in errors:
            errors.append(entry)
    if not errors:
        return None
    errors.sort(key=lambda e: (e["path"], e["rule"]))
    return {"outcome": "invalid_input", "errors": errors[:MAX_ERRORS]}
