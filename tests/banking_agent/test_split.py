"""
The split holds out about a fifth of customers, by the MD5 of their ID (ADR-0003; DML-09).
"""

import hashlib

from banking_agent.split import HELD_OUT_EVERY, held_out


def test_holds_out_a_fifth_of_customers_by_their_md5() -> None:
    ids = [f"CUS{i:06d}" for i in range(10_000)]
    share = sum(held_out(c) for c in ids) / len(ids)

    assert 0.18 < share < 0.22
    for c in ids[:50]:
        digest = hashlib.md5(c.encode(), usedforsecurity=False).hexdigest()
        assert held_out(c) == (int(digest, 16) % HELD_OUT_EVERY == 0)
