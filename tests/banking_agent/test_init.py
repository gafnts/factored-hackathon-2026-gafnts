"""
Smoke test that the package is importable from the project environment.
"""

from importlib.metadata import version

import banking_agent


def test_version_matches_distribution_metadata() -> None:
    assert banking_agent.__version__ == version("banking-agent")
