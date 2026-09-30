"""
Each event the wrapper emits is rebuilt field by field to the chat's contract: the types the chat renders pass with the
client's IDs and nothing the wrapper adds, and every other type is dropped (ADR-0004, What the chat receives, and the
amendment on the wrapper's whole input; POL-11, POL-40, CTL-04).
"""

from typing import Any

import pytest
from ag_ui.core import (
    AssistantMessage,
    CustomEvent,
    EventType,
    MessagesSnapshotEvent,
    RawEvent,
    RunAgentInput,
    RunErrorEvent,
    RunFinishedEvent,
    RunStartedEvent,
    StateSnapshotEvent,
    StepStartedEvent,
    SystemMessage,
    TextMessageContentEvent,
    ToolCallStartEvent,
    ToolMessage,
    UserMessage,
)

from banking_agent.agent.events import UnexpectedEventError, as_json, checked, rebuild

THREAD = "3f1c3c1a-0b9e-5c3e-9d7a-1f2e3d4c5b6a"


@pytest.mark.parametrize(
    "event",
    [
        StateSnapshotEvent(snapshot={"cards": [], "case": "cards"}),
        StepStartedEvent(step_name="route"),
        ToolCallStartEvent(tool_call_id="call-1", tool_call_name="list_cards"),
        CustomEvent(name="manually_emit_message", value={}),
        RawEvent(event={"secret": 1}),
    ],
)
def test_every_other_event_type_is_dropped(event: Any) -> None:
    assert rebuild(event, "thread-0001", "run-00000001") is None


def test_the_run_carries_the_clients_ids_and_nothing_the_wrapper_adds() -> None:
    echo = RunAgentInput(thread_id=THREAD, run_id="run-00000001", messages=[])
    started = RunStartedEvent(thread_id=THREAD, run_id="run-00000001", input=echo)
    finished = RunFinishedEvent(
        thread_id=THREAD, run_id="run-00000001", result={"cards": 1}
    )

    assert as_json(checked(rebuild(started, "thread-0001", "run-00000001"))) == {  # type: ignore[arg-type]
        "type": "RUN_STARTED",
        "threadId": "thread-0001",
        "runId": "run-00000001",
    }
    assert as_json(checked(rebuild(finished, "thread-0001", "run-00000001"))) == {  # type: ignore[arg-type]
        "type": "RUN_FINISHED",
        "threadId": "thread-0001",
        "runId": "run-00000001",
        "outcome": {"type": "success"},
    }


def test_the_snapshot_keeps_the_customers_messages_and_the_replies_only() -> None:
    event = MessagesSnapshotEvent(
        messages=[
            SystemMessage(id="system-0001", role="system", content="prompt"),
            UserMessage(id="user-0001", role="user", content="hola"),
            AssistantMessage(
                id="call-0001", role="assistant", content="", tool_calls=[]
            ),
            ToolMessage(
                id="tool-0001", role="tool", content="{}", tool_call_id="call-1"
            ),
            AssistantMessage(
                id="reply-0001", role="assistant", content="Sus tarjetas."
            ),
        ]
    )

    rebuilt = checked(rebuild(event, "thread-0001", "run-00000001"))  # type: ignore[arg-type]

    assert as_json(rebuilt)["messages"] == [
        {"id": "user-0001", "role": "user", "content": "hola"},
        {"id": "reply-0001", "role": "assistant", "content": "Sus tarjetas."},
    ]


@pytest.mark.parametrize(
    "event",
    [
        RunErrorEvent(message="Traceback: KeyError 'CLI-...'", code="INTERNAL_ERROR"),
        RunFinishedEvent.model_validate(
            {
                "threadId": THREAD,
                "runId": "run-00000001",
                "outcome": {
                    "type": "interrupt",
                    "interrupts": [{"id": "i-1", "reason": "controls"}],
                },
            }
        ),
    ],
)
def test_an_error_or_an_interrupt_from_the_wrapper_isnt_passed_on(event: Any) -> None:
    with pytest.raises(UnexpectedEventError):
        rebuild(event, "thread-0001", "run-00000001")


def test_an_event_that_breaks_the_contract_isnt_sent() -> None:
    event = TextMessageContentEvent(message_id="id with spaces", delta="hola")

    rebuilt = rebuild(event, "thread-0001", "run-00000001")

    assert rebuilt is not None and rebuilt.type == EventType.TEXT_MESSAGE_CONTENT
    with pytest.raises(UnexpectedEventError):
        checked(rebuilt)
