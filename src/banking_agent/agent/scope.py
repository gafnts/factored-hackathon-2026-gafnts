"""
What a request's graph run needs besides its state: the claims, the customer's token, the turn's record, and the
clients. It lives in a context variable for the request only, never in the graph's config, which LangGraph writes into
checkpoints (spike S4).
"""

from contextvars import ContextVar
from dataclasses import dataclass

from banking_agent.agent.claims import Claims
from banking_agent.agent.gateway import Gateway
from banking_agent.agent.models import Models
from banking_agent.agent.records import Turn


@dataclass(frozen=True)
class Scope:
    claims: Claims
    token: str
    turn: Turn
    gateway: Gateway
    models: Models


SCOPE: ContextVar[Scope] = ContextVar("scope")
