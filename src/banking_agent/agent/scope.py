"""
What a request's graph run needs besides its state: the claims, the customer's token, the thread's key, the turn's
record, the clients, the snapshot and business date a handoff states, and the wall clock. It lives in a context variable for the request only, never in the graph's
config, which LangGraph writes into checkpoints (spike S4).
"""

from collections.abc import Callable
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import datetime

from banking_agent.agent.claims import Claims
from banking_agent.agent.confirmations import Confirmations
from banking_agent.agent.filing import Filing
from banking_agent.agent.gateway import Gateway
from banking_agent.agent.models import Models
from banking_agent.agent.records import Turn
from banking_agent.agent.retries import RETRIES, Retries


@dataclass(frozen=True)
class Scope:
    claims: Claims
    token: str
    thread_key: str
    turn: Turn
    gateway: Gateway
    models: Models
    confirmations: Confirmations
    filing: Filing
    snapshot: str
    business_date: str
    as_of: str
    now: Callable[[], datetime]
    retries: Retries = RETRIES

    def elapsed(self) -> float:
        """
        How long the turn has run, in seconds, which the retries' deadline reads.
        """
        return self.turn.latency_ms() / 1000


SCOPE: ContextVar[Scope] = ContextVar("scope")
