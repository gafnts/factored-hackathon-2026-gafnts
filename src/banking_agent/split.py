"""
ADR-0003's split by customer, shared by the analysis, the personas, and the evaluation (ADR-0005): a customer is held
out when the MD5 of their customer_id, read as an integer, is divisible by 5, so all of a customer's rows fall on one
side.
"""

import hashlib

HELD_OUT_EVERY = 5


def held_out(customer_id: str) -> bool:
    digest = hashlib.md5(customer_id.encode(), usedforsecurity=False).hexdigest()
    return int(digest, 16) % HELD_OUT_EVERY == 0
