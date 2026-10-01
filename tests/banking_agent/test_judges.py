"""
The judges' users: created with their labels' groups and admin-written IDs, credentials on disk and never printed,
and a rotation that goes through reset (ADR-0007, Judges' access; SEC-03).
"""

import json
import string
from pathlib import Path

import pytest
from botocore.exceptions import ClientError

from banking_agent import judges
from banking_agent.dataset.lock import read_lock


class FakeCognito:
    def __init__(self, existing: set[str] | None = None) -> None:
        self.existing = existing or set()
        self.calls: list[tuple[str, dict[str, object]]] = []

    def admin_create_user(self, **kwargs: object) -> None:
        if kwargs["Username"] in self.existing:
            raise ClientError(
                {"Error": {"Code": "UsernameExistsException", "Message": ""}},
                "AdminCreateUser",
            )
        self.calls.append(("create", kwargs))

    def admin_set_user_password(self, **kwargs: object) -> None:
        self.calls.append(("password", kwargs))

    def admin_add_user_to_group(self, **kwargs: object) -> None:
        self.calls.append(("group", kwargs))

    def admin_user_global_sign_out(self, **kwargs: object) -> None:
        self.calls.append(("sign_out", kwargs))

    def admin_disable_user(self, **kwargs: object) -> None:
        self.calls.append(("disable", kwargs))

    def admin_enable_user(self, **kwargs: object) -> None:
        self.calls.append(("enable", kwargs))


IDS = {"es": "CLI-TEAM00000003", "pt": "CLI-TEAM00000005"}


def test_create_makes_each_persona_and_staff_user_with_its_groups() -> None:
    cognito = FakeCognito()

    created = judges.create(cognito, "pool", IDS)

    assert sorted(created) == ["agente", "equipo-ia", "persona-es", "persona-pt"]
    groups = {
        (c["Username"], c["GroupName"]) for kind, c in cognito.calls if kind == "group"
    }
    assert groups == {
        ("persona-es", "customer"),
        ("persona-es", "persona-es"),
        ("persona-pt", "customer"),
        ("persona-pt", "persona-pt"),
        ("agente", "human_agent"),
        ("equipo-ia", "ai_team"),
    }
    attributes = {
        c["Username"]: c["UserAttributes"]
        for kind, c in cognito.calls
        if kind == "create"
    }
    assert attributes["persona-es"] == [
        {"Name": "custom:customer_id", "Value": IDS["es"]}
    ]
    assert attributes["agente"] == []
    passwords = [c for kind, c in cognito.calls if kind == "password"]
    assert all(c["Permanent"] is True for c in passwords)


def test_every_password_carries_each_class_the_pool_requires() -> None:
    secret = judges.password()

    assert len(secret) >= 12
    assert any(c in string.ascii_lowercase for c in secret)
    assert any(c in string.ascii_uppercase for c in secret)
    assert any(c in string.digits for c in secret)
    assert any(c not in string.ascii_letters + string.digits for c in secret)


def test_an_existing_user_refuses_the_run_and_names_reset() -> None:
    cognito = FakeCognito(existing={"persona-pt"})

    with pytest.raises(judges.JudgesError, match="persona-pt.*reset"):
        judges.create(cognito, "pool", IDS)


def test_credentials_land_on_disk_owner_only_and_a_reset_updates_one(
    tmp_path: Path,
) -> None:
    path = judges.credentials_path(tmp_path, "local")

    judges.write_credentials(path, "local", {"persona-es": "a", "agente": "b"})
    judges.write_credentials(path, "local", {"persona-es": "c"})

    body = json.loads(path.read_text(encoding="utf-8"))
    assert body == {"environment": "local", "users": {"persona-es": "c", "agente": "b"}}
    assert path.stat().st_mode & 0o777 == 0o600


def test_reset_sets_a_new_password_and_signs_out_everywhere() -> None:
    cognito = FakeCognito()

    secret = judges.reset(cognito, "pool", "persona-es")

    kinds = [kind for kind, _ in cognito.calls]
    assert kinds == ["password", "sign_out"]
    assert cognito.calls[0][1]["Password"] == secret


def test_the_single_user_commands_reach_their_admin_calls() -> None:
    cognito = FakeCognito()

    judges.sign_out(cognito, "pool", "agente")
    judges.disable(cognito, "pool", "agente")
    judges.enable(cognito, "pool", "agente")

    assert [kind for kind, _ in cognito.calls] == ["sign_out", "disable", "enable"]


def test_run_prints_no_password_and_no_customer_id(tmp_path: Path) -> None:
    stack = tmp_path / "local.outputs.json"
    stack.write_text(json.dumps({"user_pool_id": {"value": "pool"}}), encoding="utf-8")
    snapshot = read_lock(Path("dataset.lock")).snapshot_id
    (tmp_path / "personas").mkdir()
    (tmp_path / "personas" / f"{snapshot}.json").write_text(
        json.dumps({"snapshot": snapshot, "personas": IDS}), encoding="utf-8"
    )
    args = judges.parse(["create", "--stack", str(stack), "--data-dir", str(tmp_path)])
    cognito = FakeCognito()

    said = judges.run(args, cognito)

    body = json.loads(
        judges.credentials_path(tmp_path, "local").read_text(encoding="utf-8")
    )
    for secret in body["users"].values():
        assert secret not in said
    for customer_id in IDS.values():
        assert customer_id not in said


def test_a_command_on_one_user_needs_the_user() -> None:
    with pytest.raises(SystemExit):
        judges.parse(["reset", "--stack", "build/local.outputs.json"])


def test_a_stack_file_that_isnt_an_outputs_file_is_refused() -> None:
    with pytest.raises(judges.JudgesError, match="outputs"):
        judges.environment(Path("build/local.json"))
