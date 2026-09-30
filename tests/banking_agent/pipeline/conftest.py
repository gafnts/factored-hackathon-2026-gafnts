"""
The fixture's base, built once per test session: tests that read it run in one xdist group, so one worker builds it.
"""

from dataclasses import dataclass
from pathlib import Path

import pytest

from banking_agent.dataset.lock import Lock
from banking_agent.dataset.snapshot import snapshot_dir
from banking_agent.pipeline import build, runner

from . import fixture


@dataclass(frozen=True)
class Built:
    lock: Lock
    lock_path: Path
    data_dir: Path
    space: runner.Workspace
    results: list[runner.Result]

    @property
    def root(self) -> Path:
        return snapshot_dir(self.data_dir, self.lock.snapshot_id)


def build_version(version: str, into: Path) -> Built:
    lock_path, data_dir, lock = fixture.install(version, into)
    space = runner.workspace(data_dir, lock.snapshot_id)
    results = build.build(lock, snapshot_dir(data_dir, lock.snapshot_id), space)
    return Built(lock, lock_path, data_dir, space, results)


@pytest.fixture(scope="session")
def base(tmp_path_factory: pytest.TempPathFactory) -> Built:
    return build_version("base", tmp_path_factory.mktemp("base"))
