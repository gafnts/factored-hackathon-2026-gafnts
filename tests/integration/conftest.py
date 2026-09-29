"""
Throwaway users in the deployed stack's pool, signed in through IAM and deleted afterwards. The stack comes from the
Terraform outputs that make integration writes; passwords and tokens stay in memory and are never printed.
"""

import base64
import contextlib
import json
import os
import secrets
import string
import uuid
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import boto3
import pytest
from botocore.exceptions import ClientError
from mypy_boto3_cognito_idp import CognitoIdentityProviderClient
from mypy_boto3_cognito_idp.type_defs import AttributeTypeTypeDef


@dataclass(frozen=True)
class User:
    username: str
    password: str
    customer_id: str | None


SignIn = Callable[[User, str], dict[str, str]]


def claims(token: str) -> dict[str, Any]:
    payload = token.split(".")[1]
    decoded: dict[str, Any] = json.loads(
        base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4))
    )
    return decoded


@pytest.fixture(scope="session")
def outputs() -> dict[str, Any]:
    path = os.environ.get("STACK_OUTPUTS")
    if not path or not Path(path).is_file():
        pytest.skip("no stack outputs; run make integration")
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return {name: value["value"] for name, value in raw.items()}


@pytest.fixture(scope="session")
def cognito() -> CognitoIdentityProviderClient:
    return boto3.client("cognito-idp", region_name="us-east-1")


@pytest.fixture(scope="session")
def users(
    outputs: dict[str, Any], cognito: CognitoIdentityProviderClient
) -> Iterator[dict[str, User]]:
    pool = outputs["user_pool_id"]
    run = uuid.uuid4().hex[:8]
    alphabet = string.ascii_letters + string.digits
    wanted = {
        "customer": (["customer"], "CLI-ITEST0000001"),
        "other_customer": (["customer"], "CLI-ITEST0000002"),
        "staff": (["human_agent"], None),
        "no_group": ([], "CLI-ITEST0000003"),
        "no_claim": (["customer"], None),
    }
    created: dict[str, User] = {}
    try:
        for role, (groups, customer_id) in wanted.items():
            user = User(
                f"it-{run}-{role.replace('_', '-')}",
                "".join(secrets.choice(alphabet) for _ in range(24)) + "aA1!",
                customer_id,
            )
            attributes: list[AttributeTypeTypeDef] = (
                [{"Name": "custom:customer_id", "Value": customer_id}]
                if customer_id
                else []
            )
            cognito.admin_create_user(
                UserPoolId=pool,
                Username=user.username,
                UserAttributes=attributes,
                MessageAction="SUPPRESS",
            )
            created[role] = user
            cognito.admin_set_user_password(
                UserPoolId=pool,
                Username=user.username,
                Password=user.password,
                Permanent=True,
            )
            for group in groups:
                cognito.admin_add_user_to_group(
                    UserPoolId=pool, Username=user.username, GroupName=group
                )
        yield created
    finally:
        for user in created.values():
            with contextlib.suppress(ClientError):
                cognito.admin_delete_user(UserPoolId=pool, Username=user.username)


@pytest.fixture(scope="session")
def sign_in(outputs: dict[str, Any], cognito: CognitoIdentityProviderClient) -> SignIn:
    def signed_in(user: User, client: str) -> dict[str, str]:
        result = cognito.admin_initiate_auth(
            UserPoolId=outputs["user_pool_id"],
            ClientId=outputs[f"{client}_client_id"],
            AuthFlow="ADMIN_USER_PASSWORD_AUTH",
            AuthParameters={"USERNAME": user.username, "PASSWORD": user.password},
        )["AuthenticationResult"]
        return {"access": result["AccessToken"], "id": result["IdToken"]}

    return signed_in
