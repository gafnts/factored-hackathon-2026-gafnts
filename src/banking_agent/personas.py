"""
The development personas (ADR-0005; ADR-0007, Judges' access): one customer per language, chosen by a fixed rule from
the pinned snapshot so that each reaches the demo's paths. The language is the persona's, not the data's: no customer in
the data writes Portuguese. Only development customers are read: the first query keeps their IDs, and every later one
joins on them (DML-09). The chosen IDs are row-level data, written under data/ and never committed or printed (SEC-03).

- es: two or more active credit cards, so a block asks which one (POL-14), one of them with a recorded limit, and a
  decline with a listed code in the last week (POL-02).
- pt: one active credit card, with a recorded limit and approved purchases in the last week, so a charge the customer
  doesn't recognize has a card to block and a purchase to dispute (the README's journey).

Both are active, have no row updated after the as-of instant, and hold no conflicting record, so the demo shows no flag
it doesn't mean to. Among those who qualify, the one with the most card transactions in the 90-day window is chosen,
so the demo has a history to list (most development customers have none), then the lowest customer_id.
"""

import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

import duckdb
from duckdb import sqltypes

from banking_agent.split import held_out

LANGUAGES = ("es", "pt")
LISTED_CODES = ("05", "14", "51", "54")
CARD_TYPES = ("Tarjeta Crédito", "Tarjeta Débito")
MAX_CARDS = 50
WINDOW = timedelta(days=90)
RECENT = timedelta(days=7)


class PersonaError(Exception):
    pass


@dataclass(frozen=True)
class Personas:
    snapshot: str
    chosen: dict[str, str]
    # How many development customers met each rule; counts, never IDs, are what gets printed.
    qualifying: dict[str, int]


def path_for(data_dir: Path, snapshot: str) -> Path:
    return data_dir / "personas" / f"{snapshot}.json"


def select(
    con: duckdb.DuckDBPyConnection, snapshot: str, business_date: date, as_of: datetime
) -> Personas:
    """
    Reads the raw_customers, raw_products, and raw_transactions views that analysis.source.connect opens.
    """
    con.create_function("held_out", held_out, [sqltypes.VARCHAR], sqltypes.BOOLEAN)
    con.execute(
        "create or replace temp table development_ids as "
        "select customer_id from raw_customers where not held_out(customer_id)"
    )
    con.execute(
        "create or replace temp table persona_customers as "
        "select c.customer_id, c.customer_status, cast(c.last_updated as timestamp) as last_updated "
        "from raw_customers c join development_ids d on d.customer_id = c.customer_id "
        "where cast(c.registration_date as timestamp) <= $as_of",
        {"as_of": as_of},
    )
    con.execute(
        "create or replace temp table persona_cards as "
        "select p.product_id, p.customer_id, p.product_type, p.product_status, "
        "  cast(p.credit_limit as decimal(15,2)) as credit_limit, "
        "  cast(p.opening_date as date) as opening_date, "
        "  cast(p.expiration_date as date) as expiration_date, "
        "  cast(p.last_updated as timestamp) as last_updated "
        "from raw_products p join persona_customers c on c.customer_id = p.customer_id "
        "where list_contains($card_types, p.product_type) and cast(p.opening_date as date) <= $as_of",
        {"card_types": list(CARD_TYPES), "as_of": as_of},
    )
    con.execute(
        "create or replace temp table persona_transactions as "
        "select k.customer_id, k.product_id, k.product_type, k.product_status, "
        "  cast(t.transaction_date as timestamp) as transaction_date, t.transaction_type, "
        "  t.transaction_status, t.response_code, "
        "  cast(cast(t.transaction_date as timestamp) as date) < k.opening_date as before_card_opening, "
        "  coalesce(cast(cast(t.transaction_date as timestamp) as date) > k.expiration_date, false) "
        "    as after_card_expiration "
        "from raw_transactions t join persona_cards k on k.product_id = t.product_id "
        "where cast(t.transaction_date as timestamp) > $start "
        "  and cast(t.transaction_date as timestamp) <= $as_of",
        {"start": as_of - WINDOW, "as_of": as_of},
    )
    rules = {
        "es": """
            (select count(*) from persona_cards k where k.customer_id = c.customer_id
              and k.product_type = 'Tarjeta Crédito' and k.product_status = 'Active') >= 2
            and exists (select 1 from persona_cards k where k.customer_id = c.customer_id
              and k.product_type = 'Tarjeta Crédito' and k.product_status = 'Active'
              and k.credit_limit is not null)
            and exists (select 1 from persona_transactions t where t.customer_id = c.customer_id
              and t.product_status = 'Active' and t.transaction_status = 'Declined'
              and list_contains($codes, t.response_code) and t.transaction_date > $recent)
        """,
        "pt": """
            (select count(*) from persona_cards k where k.customer_id = c.customer_id
              and k.product_type = 'Tarjeta Crédito' and k.product_status = 'Active') = 1
            and exists (select 1 from persona_cards k where k.customer_id = c.customer_id
              and k.product_type = 'Tarjeta Crédito' and k.product_status = 'Active'
              and k.credit_limit is not null
              and exists (select 1 from persona_transactions t where t.product_id = k.product_id
                and t.transaction_type = 'Purchase' and t.transaction_status = 'Approved'
                and t.transaction_date > $recent))
        """,
    }
    clean = """
        c.customer_status = 'Active' and c.last_updated <= $as_of
        and (select count(*) from persona_cards k where k.customer_id = c.customer_id) <= $max_cards
        and not exists (select 1 from persona_cards k where k.customer_id = c.customer_id
          and (k.last_updated > $as_of
            or (k.product_status = 'Active' and k.expiration_date < $business_date)))
        and not exists (select 1 from persona_transactions t where t.customer_id = c.customer_id
          and (t.before_card_opening or t.after_card_expiration))
    """
    parameters = {
        "as_of": as_of,
        "business_date": business_date,
        "recent": as_of - RECENT,
        "codes": list(LISTED_CODES),
        "max_cards": MAX_CARDS,
    }
    chosen: dict[str, str] = {}
    qualifying: dict[str, int] = {}
    for language in LANGUAGES:
        rows = con.execute(
            f"select customer_id from persona_customers c where {clean} and {rules[language]} "
            "order by (select count(*) from persona_transactions t where t.customer_id = c.customer_id) desc, "
            "customer_id",
            {k: v for k, v in parameters.items() if f"${k}" in clean + rules[language]},
        ).fetchall()
        if not rows:
            raise PersonaError(
                f"no development customer meets the {language} persona's rule"
            )
        chosen[language] = rows[0][0]
        qualifying[language] = len(rows)
    return Personas(snapshot, chosen, qualifying)


def write(path: Path, personas: Personas) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = {"snapshot": personas.snapshot, "personas": personas.chosen}
    path.write_text(json.dumps(body, indent=2) + "\n", encoding="utf-8")


def read(path: Path, snapshot: str) -> dict[str, str]:
    if not path.is_file():
        raise PersonaError(f"{path} not found; run make personas")
    body = json.loads(path.read_text(encoding="utf-8"))
    if body.get("snapshot") != snapshot or sorted(body.get("personas", {})) != sorted(
        LANGUAGES
    ):
        raise PersonaError(
            f"{path} doesn't hold snapshot {snapshot}'s personas; run make personas"
        )
    chosen: dict[str, str] = body["personas"]
    if any(held_out(customer_id) for customer_id in chosen.values()):
        raise PersonaError(f"{path} names a held-out customer")
    return chosen
