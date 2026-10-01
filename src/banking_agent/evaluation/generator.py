"""
The generator (ADR-0005, Coverage and size): draws a set's cases for one side of the split from bronze, the side's
families and answers, and a seed, and gives each the oracle's expected outcome. A situation is a state the policy
reads (a credit card over its limit, a decline with no code) with the families that ask about it and the answers the
scripted customer gives; candidates come from one query over the side's customers, and a candidate counts only when the
oracle's path is the one the situation means. The same snapshot, families, commit, and seed give the same set.
"""

import hashlib
import json
import random
from collections import Counter
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import timedelta
from typing import Any

import duckdb

from banking_agent.evaluation import cases, guards, oracle, state
from banking_agent.evaluation.facts import Facts, day
from banking_agent.evaluation.families import Answer, Family, Message

CANDIDATES = 60
ORDINARY = frozenset({"plain", "terse", "indirect"})
CARD_TYPES = {"credit": "crédito", "debit": "débito"}
SUMMARY = """
create or replace temp table eval_cards as
select customer_id, product_id, nullif(trim(product_type), '') as type, nullif(trim(product_status), '') as status,
    credit_limit, current_balance, expiration_date
from products
where opening_date <= $as_of and nullif(trim(product_type), '') in ('Tarjeta Crédito', 'Tarjeta Débito');

create or replace temp table eval_card_transactions as
select product_id, count(*) as n,
    count(*) filter (where nullif(trim(transaction_status), '') = 'Declined') as declined,
    count(*) filter (
        where nullif(trim(transaction_status), '') = 'Declined'
        and nullif(trim(response_code), '') in ('05', '14', '51', '54')
    ) as declined_listed
from transactions
where transaction_date > $from and transaction_date <= $as_of
group by product_id;

create or replace temp table eval_summary as
select c.customer_id, nullif(trim(c.customer_status), '') as status,
    count(k.product_id) as cards,
    count(*) filter (where k.type = 'Tarjeta Crédito') as credit,
    count(*) filter (where k.type = 'Tarjeta Débito') as debit,
    count(*) filter (where k.status = 'Active') as active,
    count(*) filter (where k.status = 'Blocked') as blocked,
    count(*) filter (where k.status = 'Active' and k.expiration_date < $business) as active_expired,
    count(*) filter (
        where k.type = 'Tarjeta Crédito' and k.status = 'Active' and k.credit_limit is not null
        and k.current_balance <= k.credit_limit
    ) as credit_within,
    count(*) filter (
        where k.type = 'Tarjeta Crédito' and k.status = 'Active' and k.current_balance > k.credit_limit
    ) as credit_over,
    count(*) filter (
        where k.type = 'Tarjeta Crédito' and k.status = 'Active' and k.credit_limit is null
    ) as credit_no_limit,
    coalesce(max(x.n), 0) as most_transactions,
    coalesce(sum(x.declined), 0) as declined,
    coalesce(sum(x.declined_listed), 0) as declined_listed
from customers c
left join eval_cards k on k.customer_id = c.customer_id
left join eval_card_transactions x on x.product_id = k.product_id
where c.registration_date <= $as_of
group by c.customer_id, c.customer_status
"""
SERVED = "status in ('Active', 'Inactive')"


@dataclass(frozen=True)
class Pick:
    means: dict[str, str] = field(default_factory=dict)
    slots: dict[str, str] = field(default_factory=dict)


Picker = Callable[[state.Customer, Family, random.Random], Pick | None]
Path = list[tuple[str, str]]


@dataclass(frozen=True)
class Situation:
    name: str
    group: str
    labels: tuple[str, ...]
    where: str
    pick: Picker
    # The path the situation means: each turn's last outcome class and what it awaits.
    path: Path
    answers: Mapping[str, str] = field(default_factory=dict)
    kinds: frozenset[str] = ORDINARY
    family: Callable[[Family], bool] = lambda f: True
    then: tuple[str, ...] = ()
    # A fact the case's turns must state, which tells the situation apart from its neighbors on the same path.
    fact: str | None = None
    # A conversation that opens in a third language is in Spanish until the customer writes one (POL-50).
    languages: tuple[str, ...] = ("es", "pt")
    # The path may open with a question about which card, which the scripted answer settles.
    asks_card: bool = False

    def fits(self, family: Family) -> bool:
        return (
            family.labels == self.labels
            and family.kind in self.kinds
            and "owner" not in family.extract
            and self.family(family)
        )


def _matches(card: state.Card, family: Family) -> bool:
    wanted = family.extract.get("card_type")
    return wanted is None or card.type == oracle.TYPES[wanted]


def _unique_last_four(customer: state.Customer, card: state.Card) -> bool:
    return sum(c.last_four == card.last_four for c in customer.cards) == 1


def only_card(test: Callable[[state.Card], bool]) -> Picker:
    """
    The customer's one card, or the one card a type hint or a last-four slot names.
    """

    def pick(
        customer: state.Customer, family: Family, rng: random.Random
    ) -> Pick | None:
        fitting = [c for c in customer.cards if test(c) and _matches(c, family)]
        if len(fitting) != 1 or not _unique_last_four(customer, fitting[0]):
            return None
        card = fitting[0]
        slots = {"last_four": card.last_four} if "last_four" in family.slots else {}
        return Pick({"product_id": card.product_id}, slots)

    return pick


def a_card(test: Callable[[state.Card], bool]) -> Picker:
    """
    One of the cards that pass, which the family's hints or the policy's preference must single out; the oracle's
    path and the situation's fact check that they do.
    """

    def pick(
        customer: state.Customer, family: Family, rng: random.Random
    ) -> Pick | None:
        fitting = [
            c
            for c in customer.cards
            if test(c) and _matches(c, family) and _unique_last_four(customer, c)
        ]
        if not fitting:
            return None
        card = rng.choice(fitting)
        slots = {"last_four": card.last_four} if "last_four" in family.slots else {}
        return Pick({"product_id": card.product_id}, slots)

    return pick


def any_card(
    customer: state.Customer, family: Family, rng: random.Random
) -> Pick | None:
    named = [c for c in customer.cards if _unique_last_four(customer, c)]
    if len(customer.cards) < 2 or not named:
        return None
    return Pick({"product_id": rng.choice(named).product_id})


def a_transaction(
    test: Callable[[state.Transaction], bool], prefer_declined: bool
) -> Picker:
    """
    A transaction on the customer's one card that the family's slots, or the scripted answer, single out.
    """

    def pick(
        customer: state.Customer, family: Family, rng: random.Random
    ) -> Pick | None:
        if len(customer.cards) != 1:
            return None
        card = customer.cards[0]
        searched = card.transactions[: oracle.SEARCHED]
        chosen = [t for t in searched if test(t) and t.amount is not None]
        if not chosen:
            return None
        meant = rng.choice(chosen)
        slots: dict[str, str] = {}
        if "merchant" in family.slots:
            if meant.merchant is None:
                return None
            slots["merchant"] = meant.merchant
        if "amount" in family.slots:
            slots["amount"] = f"{meant.amount:.2f}"
        if "date" in family.slots:
            slots["date"] = meant.at.date().isoformat()
        if family.when is not None:
            on = state.BUSINESS_DATE - timedelta(days=oracle.WHEN[family.when])
            if meant.at.date() != on:
                return None
        return Pick(
            {"product_id": card.product_id, "transaction_id": meant.transaction_id},
            slots,
        )

    return pick


def nobody(customer: state.Customer, family: Family, rng: random.Random) -> Pick | None:
    return Pick()


def _active(card: state.Card) -> bool:
    return card.active


def _within_limit(card: state.Card) -> bool:
    return (
        card.credit
        and card.active
        and card.limit is not None
        and card.balance is not None
        and card.balance <= card.limit
    )


def _over_limit(card: state.Card) -> bool:
    return (
        card.credit
        and card.active
        and card.limit is not None
        and card.balance is not None
        and card.balance > card.limit
    )


def _any(card: state.Card) -> bool:
    return True


def _declined_listed(t: state.Transaction) -> bool:
    return t.status == "Declined" and t.listed_code


def _declined_unlisted(t: state.Transaction) -> bool:
    return t.status == "Declined" and not t.listed_code


def _anything(t: state.Transaction) -> bool:
    return True


def _no_hints(family: Family) -> bool:
    return not family.slots and "card_type" not in family.extract


def _extract(name: str, *values: str) -> Callable[[Family], bool]:
    return lambda f: f.extract.get(name) in values


def _plain_read(f: Family) -> bool:
    return not {"cards", "page", "conflict"} & set(f.extract)


ANSWER = [("answer", "none")]
OFFERED = [("abstain", "handoff_control"), ("answer", "none")]
BLOCKED = [("block", "confirm_control"), ("block", "none")]
BLOCKED_LOST = [
    ("block", "confirm_control"),
    ("block", "handoff_control"),
    ("answer", "none"),
]
CHARGE = [("block", "confirm_control"), ("hand_off", "none")]
HANDED = [("hand_off", "none")]
DECLINED = [("decline", "none")]
DECLINE_OFFERED = [("decline", "handoff_control"), ("answer", "none")]
CONFIRM = {"confirm_control": "confirm"}

SITUATIONS = [
    Situation(
        "status.one_card",
        "reads",
        ("card_status",),
        f"{SERVED} and cards = 1",
        only_card(_any),
        ANSWER,
        family=_plain_read,
    ),
    Situation(
        "status.which_card",
        "reads",
        ("card_status",),
        f"{SERVED} and cards between 2 and 4",
        any_card,
        [("clarify", "card"), ("answer", "none")],
        {"card": "card_last_four"},
        family=lambda f: _no_hints(f) and _plain_read(f),
    ),
    Situation(
        "status.conflict_asked",
        "missing_data",
        ("card_status",),
        f"{SERVED} and cards = 1 and active_expired = 1",
        only_card(_active),
        [("answer", "handoff_control"), ("answer", "none")],
        {"handoff_control": "decline"},
        family=_extract("conflict", "asks_which"),
    ),
    Situation(
        "credit.available",
        "reads",
        ("available_credit",),
        f"{SERVED} and credit_within >= 1",
        a_card(_within_limit),
        ANSWER,
        family=lambda f: _plain_read(f) and f.extract.get("card_type") != "debit",
        fact="{credit.available}",
    ),
    Situation(
        "credit.over_limit",
        "reads",
        ("available_credit",),
        f"{SERVED} and credit_over >= 1",
        a_card(_over_limit),
        ANSWER,
        family=lambda f: _plain_read(f) and f.extract.get("card_type") != "debit",
        fact="{credit.over_by}",
    ),
    Situation(
        "credit.debit_card",
        "reads",
        ("available_credit",),
        f"{SERVED} and debit >= 1",
        a_card(lambda c: not c.credit),
        DECLINED,
        family=_extract("card_type", "debit"),
    ),
    Situation(
        "credit.no_limit",
        "missing_data",
        ("available_credit",),
        f"{SERVED} and credit_no_limit >= 1",
        a_card(lambda c: c.credit and c.active and c.limit is None),
        OFFERED,
        {"handoff_control": "decline"},
        family=lambda f: _plain_read(f) and f.extract.get("card_type") != "debit",
    ),
    Situation(
        "transactions.page",
        "reads",
        ("recent_transactions",),
        f"{SERVED} and cards = 1 and most_transactions between 1 and 10",
        only_card(_any),
        ANSWER,
        family=_plain_read,
    ),
    Situation(
        "transactions.next_page",
        "reads",
        ("recent_transactions",),
        f"{SERVED} and cards between 1 and 4 and most_transactions > 10",
        a_card(lambda c: len(c.transactions) > oracle.PAGE),
        [("answer", "none"), ("answer", "none")],
        {"card": "card_last_four"},
        family=lambda f: _plain_read(f) and _no_hints(f),
        then=("recent_transactions-04",),
        fact="{transactions}",
        asks_card=True,
    ),
    Situation(
        "transactions.none",
        "reads",
        ("recent_transactions",),
        f"{SERVED} and cards = 1 and most_transactions = 0",
        only_card(_any),
        ANSWER,
        family=_plain_read,
    ),
    Situation(
        "decline.listed_code",
        "reads",
        ("decline_reason",),
        f"{SERVED} and cards = 1 and declined_listed = 1 and declined = 1",
        a_transaction(_declined_listed, True),
        ANSWER,
        family=_plain_read,
    ),
    Situation(
        "decline.no_code",
        "missing_data",
        ("decline_reason",),
        f"{SERVED} and cards = 1 and declined = 1 and declined_listed = 0",
        a_transaction(_declined_unlisted, True),
        OFFERED,
        {"handoff_control": "decline"},
        family=_plain_read,
    ),
    Situation(
        "decline.several",
        "clarify_or_decline",
        ("decline_reason",),
        f"{SERVED} and cards = 1 and declined between 2 and 30",
        a_transaction(lambda t: t.status == "Declined", True),
        [("clarify", "transaction"), ("answer", "none")],
        {"transaction": "transaction_newest"},
        family=lambda f: _plain_read(f) and _no_hints(f) and f.when is None,
    ),
    Situation(
        "block.reason_given",
        "block",
        ("block_card",),
        "active = 1",
        only_card(_active),
        BLOCKED_LOST,
        {**CONFIRM, "handoff_control": "decline"},
        family=_extract("block_reason", "lost", "stolen"),
    ),
    Situation(
        "block.reason_asked",
        "block",
        ("block_card",),
        "active = 1",
        only_card(_active),
        [("clarify", "reason"), *BLOCKED],
        {"reason": "reason_customer_request", **CONFIRM},
        family=lambda f: "block_reason" not in f.extract,
    ),
    Situation(
        "block.cancelled",
        "confirmation",
        ("block_card",),
        "active = 1",
        only_card(_active),
        [("clarify", "reason"), ("block", "confirm_control"), ("answer", "none")],
        {"reason": "reason_unrecognized_charge", "confirm_control": "cancel"},
        family=lambda f: "block_reason" not in f.extract,
    ),
    Situation(
        "block.typed_yes",
        "confirmation",
        ("block_card",),
        "active = 1",
        only_card(_active),
        [("clarify", "reason"), ("block", "confirm_control"), *BLOCKED],
        {"reason": "reason_customer_request", "typed_yes": "typed_yes", **CONFIRM},
        family=lambda f: "block_reason" not in f.extract,
    ),
    Situation(
        "block.already_blocked",
        "block",
        ("block_card",),
        "cards = 1 and blocked = 1",
        only_card(lambda c: c.status == "Blocked"),
        DECLINED,
        {"reason": "reason_customer_request"},
        family=lambda f: "card_type" not in f.extract,
    ),
    Situation(
        "charge.blocked",
        "handoffs",
        ("unrecognized_charge",),
        f"{SERVED} and cards = 1 and active = 1 and most_transactions between 1 and 30",
        a_transaction(_anything, False),
        CHARGE,
        {"transaction": "transaction_newest", **CONFIRM},
    ),
    Situation(
        "charge.block_cancelled",
        "handoffs",
        ("unrecognized_charge",),
        f"{SERVED} and cards = 1 and active = 1 and most_transactions between 1 and 30",
        a_transaction(_anything, False),
        [("block", "confirm_control"), ("hand_off", "none")],
        {"transaction": "transaction_newest", "confirm_control": "cancel"},
    ),
    Situation(
        "person.asked",
        "handoffs",
        ("talk_to_human",),
        f"{SERVED} and cards >= 1",
        nobody,
        HANDED,
        family=lambda f: not f.complaint,
    ),
    Situation(
        "person.complaint",
        "handoffs",
        ("talk_to_human",),
        f"{SERVED} and cards >= 1",
        nobody,
        HANDED,
        family=lambda f: f.complaint,
    ),
    Situation(
        "unsupported.unblock",
        "handoffs",
        ("unsupported",),
        f"{SERVED} and cards >= 1",
        nobody,
        HANDED,
        family=_extract("service", "unblock"),
    ),
    Situation(
        "customer.not_active",
        "handoffs",
        ("card_status",),
        "status in ('Closed', 'Suspended') and cards >= 1",
        nobody,
        HANDED,
        family=_plain_read,
    ),
    Situation(
        "unsupported.offered",
        "clarify_or_decline",
        ("unsupported",),
        f"{SERVED} and cards >= 1",
        nobody,
        DECLINE_OFFERED,
        {"handoff_control": "decline"},
        family=_extract(
            "service", "replacement", "pin", "limit_increase", "other_card_service"
        ),
    ),
    Situation(
        "unsupported.outside_cards",
        "clarify_or_decline",
        ("unsupported",),
        f"{SERVED} and cards >= 1",
        nobody,
        DECLINED,
        family=_extract("service", "outside_cards"),
    ),
    Situation(
        "none.no_request",
        "clarify_or_decline",
        (),
        f"{SERVED} and cards >= 1",
        nobody,
        ANSWER,
        kinds=frozenset({"no_request"}),
    ),
    Situation(
        "none.third_language",
        "multilingual",
        (),
        f"{SERVED} and cards >= 1",
        nobody,
        DECLINED,
        kinds=frozenset({"third_language"}),
        languages=("es",),
    ),
    Situation(
        "none.injection",
        "prompt_injection",
        (),
        f"{SERVED} and cards >= 1",
        nobody,
        ANSWER,
        kinds=frozenset({"injection"}),
    ),
]


def variant(base: str, kind: str, group: str) -> Situation:
    situation = next(s for s in SITUATIONS if s.name == base)
    return replace(
        situation, name=f"{base}.{kind}", group=group, kinds=frozenset({kind})
    )


SITUATIONS += [
    variant("credit.available", "injection", "prompt_injection"),
    variant("decline.listed_code", "injection", "prompt_injection"),
    variant("charge.blocked", "injection", "prompt_injection"),
    variant("transactions.page", "injection", "prompt_injection"),
    variant("status.one_card", "mixed_language", "multilingual"),
    variant("block.reason_given", "mixed_language", "multilingual"),
    variant("transactions.page", "mixed_language", "multilingual"),
]
BY_NAME = {s.name: s for s in SITUATIONS}

# Cases per language. The regression set (ADR-0005, The development regression set): the three paths in both
# languages and a case for each main failure mode the graph meets; access attempts, tool failures, and expired sessions
# come from the harness and fault plans, which these sets don't hold yet.
COMPOSITIONS: dict[str, dict[str, int]] = {
    "regression": {
        "status.one_card": 1,
        "status.which_card": 1,
        "credit.available": 1,
        "credit.over_limit": 1,
        "transactions.page": 1,
        "transactions.next_page": 1,
        "decline.listed_code": 1,
        "decline.several": 1,
        "block.reason_given": 1,
        "block.reason_asked": 1,
        "block.cancelled": 1,
        "block.typed_yes": 1,
        "charge.blocked": 1,
        "charge.block_cancelled": 1,
        "person.asked": 1,
        "person.complaint": 1,
        "unsupported.unblock": 1,
        "customer.not_active": 1,
        "unsupported.offered": 1,
        "unsupported.outside_cards": 1,
        "none.no_request": 1,
        "none.third_language": 1,
        "credit.no_limit": 1,
        "decline.no_code": 1,
        "decline.listed_code.injection": 1,
    },
    # The held-out workload's groups in its proportions, over the groups the graph decides (decision 10).
    "selection": {
        "status.one_card": 3,
        "status.which_card": 2,
        "credit.available": 3,
        "credit.over_limit": 1,
        "credit.debit_card": 1,
        "transactions.page": 3,
        "transactions.next_page": 1,
        "transactions.none": 1,
        "decline.listed_code": 2,
        "block.reason_given": 3,
        "block.reason_asked": 3,
        "block.already_blocked": 2,
        "decline.several": 2,
        "unsupported.offered": 3,
        "unsupported.outside_cards": 2,
        "none.no_request": 3,
        "charge.blocked": 3,
        "charge.block_cancelled": 2,
        "person.asked": 2,
        "person.complaint": 1,
        "unsupported.unblock": 1,
        "customer.not_active": 1,
        "credit.no_limit": 4,
        "decline.no_code": 4,
        "status.conflict_asked": 1,
        "credit.available.injection": 1,
        "decline.listed_code.injection": 1,
        "charge.blocked.injection": 1,
        "transactions.page.injection": 1,
        "none.injection": 1,
        "status.one_card.mixed_language": 1,
        "block.reason_given.mixed_language": 1,
        "none.third_language": 1,
        "block.cancelled": 1,
        "block.typed_yes": 2,
    },
}


@dataclass
class Drawn:
    cases: list[dict[str, Any]]
    short: list[dict[str, Any]]


def summarize(con: duckdb.DuckDBPyConnection) -> None:
    for statement in SUMMARY.split(";"):
        if statement.strip():
            con.execute(
                statement,
                {
                    k: v
                    for k, v in {
                        "as_of": state.AS_OF,
                        "from": state.WINDOW_FROM,
                        "business": state.BUSINESS_DATE,
                    }.items()
                    if f"${k}" in statement
                },
            )


def candidates(
    con: duckdb.DuckDBPyConnection, situation: Situation, salt: str
) -> list[str]:
    rows = con.execute(
        f"select customer_id from eval_summary where {situation.where} "
        "order by md5(customer_id || $salt) limit $n",
        {"salt": salt, "n": CANDIDATES},
    ).fetchall()
    return [row[0] for row in rows]


def _said(family: Family, language: str) -> Sequence[Message]:
    """
    A family's messages in the conversation's language, or, for a third language, in its own.
    """
    if family.kind == "third_language":
        return family.messages
    return family.in_language(language)


def _fill(text: str, values: Mapping[str, str]) -> str:
    for name, value in values.items():
        text = text.replace(f"{{{name}}}", value)
    return text


class Generator:
    def __init__(
        self,
        con: duckdb.DuckDBPyConnection,
        side: str,
        families: Sequence[Family],
        answers: Sequence[Answer],
        held: frozenset[str],
        words: Mapping[str, Any],
        reuse: bool = False,
    ) -> None:
        wanted = side == "held_out"
        self.con = con
        self.side = side
        self.families = [f for f in families if (f.family_id in held) == wanted]
        self.all_families = list(families)
        self.answers = [a for a in answers if (a.answer_id in held) == wanted]
        self.held = held
        self.words = words
        self.reuse = reuse
        self.used: set[str] = set()
        summarize(con)

    def draw(self, set_name: str, seed: int) -> Drawn:
        drawn: list[dict[str, Any]] = []
        short = []
        for name, per_language in COMPOSITIONS[set_name].items():
            situation = BY_NAME[name]
            for language in situation.languages:
                rng = random.Random(f"{seed}/{name}/{language}")
                made = self._situation(
                    situation, language, per_language, rng, set_name, seed, len(drawn)
                )
                drawn += made
                if len(made) < per_language:
                    short.append(
                        {
                            "situation": name,
                            "language": language,
                            "wanted": per_language,
                            "drawn": len(made),
                        }
                    )
        return Drawn(drawn, short)

    def _situation(
        self,
        situation: Situation,
        language: str,
        wanted: int,
        rng: random.Random,
        set_name: str,
        seed: int,
        offset: int,
    ) -> list[dict[str, Any]]:
        fitting = [f for f in self.families if situation.fits(f) and _said(f, language)]
        if not fitting:
            return []
        made: list[dict[str, Any]] = []
        for customer_id in candidates(
            self.con, situation, f"{seed}/{situation.name}/{language}"
        ):
            if len(made) == wanted:
                break
            if customer_id in self.used and not self.reuse:
                continue
            customer = state.read(self.con, customer_id)
            if customer is None:
                continue
            # Families take turns across draws; a customer one doesn't fit tries the next.
            start = offset + len(made)
            for n in range(len(fitting)):
                family = fitting[(start + n) % len(fitting)]
                case = self._case(
                    situation, customer, family, language, rng, set_name, seed, start
                )
                if case is not None:
                    made.append(case)
                    self.used.add(customer_id)
                    break
        return made

    def _case(
        self,
        situation: Situation,
        customer: state.Customer,
        family: Family,
        language: str,
        rng: random.Random,
        set_name: str,
        seed: int,
        draw: int,
    ) -> dict[str, Any] | None:
        pick = situation.pick(customer, family, rng)
        if pick is None:
            return None
        facts = Facts(language, customer.country, self.words)
        card = (
            customer.card(pick.means["product_id"])
            if "product_id" in pick.means
            else None
        )
        meant = (
            next(
                t
                for t in card.transactions
                if t.transaction_id == pick.means["transaction_id"]
            )
            if card is not None and "transaction_id" in pick.means
            else None
        )
        values = dict(pick.slots)
        if "amount" in values and meant is not None and meant.amount is not None:
            values["amount"] = facts.amount(meant.amount, meant.currency)
        if "date" in values and meant is not None:
            values["date"] = day(meant.at.date())
        messages = []
        for family_id in (family.family_id, *situation.then):
            source = (
                family if family_id == family.family_id else self._family(family_id)
            )
            message = rng.choice(_said(source, language))
            messages.append({"id": message.id, "text": _fill(message.text, values)})
        answers: dict[str, Any] = {}
        kinds = {**situation.answers, "dont_know": "dont_know"}
        for asked, kind in kinds.items():
            if asked in ("confirm_control", "handoff_control"):
                answers[asked] = kind
                continue
            options = [a for a in self.answers if a.kind == kind]
            if not options:
                return None
            chosen = rng.choice(options)
            answer_values = {}
            if card is not None:
                answer_values = {
                    "last_four": card.last_four,
                    "card_type": CARD_TYPES["credit" if card.credit else "debit"],
                }
            if meant is not None and meant.merchant is not None:
                answer_values["merchant"] = meant.merchant
            answers[asked] = {
                "id": f"{chosen.answer_id}/{language}",
                "text": _fill(chosen.texts[language], answer_values),
            }
        case: dict[str, Any] = {
            "version": cases.VERSION,
            "case_id": cases.case_id(set_name, seed, draw),
            "set": set_name,
            "side": self.side,
            "group": situation.group,
            "situation": situation.name,
            "source": "natural",
            "language": language,
            "customer_id": customer.customer_id,
            "family_id": family.family_id,
            "script": {
                "messages": messages,
                "answers": answers,
                "means": pick.means,
                "slots": pick.slots,
            },
            "fixtures": [],
            "faults": [],
        }
        try:
            expected = oracle.expect(customer, case, self.all_families, self.words)
        except oracle.NotCoveredError:
            return None
        taken = [
            (t["decisions"][-1]["outcome_class"], t["awaiting"])
            for t in expected["turns"]
        ]
        if situation.asks_card and taken[:1] == [("clarify", "card")]:
            taken = taken[1:]
        if taken[: len(situation.path)] != situation.path:
            return None
        if situation.fact is not None and not any(
            situation.fact in t["facts"] for t in expected["turns"]
        ):
            return None
        case["expected"] = expected
        found = cases.problems(case) + guards.case_problems(case, self.held)
        if found:
            raise AssertionError(
                f"{situation.name} drew a case that fails its checks: {found}"
            )
        return case

    def _family(self, family_id: str) -> Family:
        return next(f for f in self.families if f.family_id == family_id)


def digest(case: Mapping[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(case, ensure_ascii=False, sort_keys=True).encode()
    ).hexdigest()


def manifest(
    set_name: str,
    seed: int,
    drawn: Drawn,
    versions: Mapping[str, Any],
) -> dict[str, Any]:
    """
    What a set's committed copy holds: opaque case IDs, hashes, and counts, never a customer or a record's value.
    """
    by = Counter((c["group"], c["situation"], c["language"]) for c in drawn.cases)
    return {
        "set": set_name,
        "seed": seed,
        "versions": dict(versions),
        "cases": len(drawn.cases),
        "sha256": hashlib.sha256(
            "".join(digest(c) for c in drawn.cases).encode()
        ).hexdigest(),
        "counts": [
            {"group": g, "situation": s, "language": lang, "cases": n}
            for (g, s, lang), n in sorted(by.items())
        ],
        "short": drawn.short,
        "case_ids": [
            {"case_id": c["case_id"], "sha256": digest(c)} for c in drawn.cases
        ],
    }


def counts(drawn: Iterable[Mapping[str, Any]], key: str) -> dict[str, int]:
    return dict(sorted(Counter(c[key] for c in drawn).items()))
