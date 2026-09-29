"""
The deployed stack holds its boundaries: each user signs in through their side's client only, a customer can't rewrite
their customer_id, the Gateway and Cedar serve a customer their own ID only, the Runtime accepts customers' access
tokens only, and every log group keeps a retention (ADR-0004, To verify on the first deploy; ADR-0007, Sign-in; POL-07,
POL-08; SEC-04, SEC-05; EVL-04; OPS-10). Spikes S3 and S4 found each of these by hand.
"""

import json
import uuid
from typing import Any

import boto3
import httpx
import pytest
from botocore import UNSIGNED
from botocore.config import Config
from botocore.exceptions import ClientError
from mypy_boto3_cognito_idp import CognitoIdentityProviderClient

from banking_agent.agent.app import REPLY

from .conftest import SignIn, User, claims

pytestmark = pytest.mark.integration

DENIED = -32002


def mcp(
    outputs: dict[str, Any], token: str | None, method: str, params: dict[str, Any]
) -> tuple[int, Any]:
    headers = {"Accept": "application/json, text/event-stream"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    body = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
    response = httpx.post(
        outputs["gateway_url"], json=body, headers=headers, timeout=30
    )
    text = response.text
    if response.headers.get("content-type", "").startswith("text/event-stream"):
        text = next(
            (ln[5:].strip() for ln in text.splitlines() if ln.startswith("data:")), ""
        )
    try:
        return response.status_code, json.loads(text)
    except json.JSONDecodeError:
        return response.status_code, text


def call(
    outputs: dict[str, Any], token: str, tool: str, arguments: dict[str, Any]
) -> dict[str, Any]:
    name = f"{outputs['gateway_target']}___{tool}"
    status, body = mcp(
        outputs, token, "tools/call", {"name": name, "arguments": arguments}
    )
    assert status == 200
    assert isinstance(body, dict)
    return body


def tool_output(body: dict[str, Any]) -> dict[str, Any]:
    text = body["result"]["content"][0]["text"]
    output: dict[str, Any] = json.loads(text)
    return output


def get_card(customer_id: str, card_id: str = "PRD-ITEST0000001") -> dict[str, Any]:
    return {
        "customer_id": customer_id,
        "origin_jti": str(uuid.uuid4()),
        "card_id": card_id,
    }


def invoke(
    outputs: dict[str, Any], token: str | None, origin: str | None = None
) -> httpx.Response:
    headers = {
        "Accept": "text/event-stream",
        "X-Amzn-Bedrock-AgentCore-Runtime-Session-Id": f"it-session-{uuid.uuid4().hex}",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    body = {
        "threadId": f"thread-{uuid.uuid4().hex[:12]}",
        "runId": f"run-{uuid.uuid4().hex[:12]}",
        "state": {},
        "messages": [{"id": uuid.uuid4().hex, "role": "user", "content": "Hola"}],
        "tools": [],
        "context": [],
        "forwardedProps": {},
    }
    return httpx.post(outputs["invoke_url"], json=body, headers=headers, timeout=120)


def events(response: httpx.Response) -> list[dict[str, Any]]:
    return [
        json.loads(line.removeprefix("data:"))
        for line in response.text.splitlines()
        if line.startswith("data:")
    ]


# Sign-in (ADR-0007)


def test_a_customers_access_token_carries_their_customer_id_and_group(
    users: dict[str, User], sign_in: SignIn
) -> None:
    token = claims(sign_in(users["customer"], "customer")["access"])

    assert token["customer_id"] == users["customer"].customer_id
    assert "customer" in token["cognito:groups"]


def test_a_staff_token_carries_no_customer_id(
    users: dict[str, User], sign_in: SignIn
) -> None:
    token = claims(sign_in(users["staff"], "staff")["access"])

    assert "customer_id" not in token
    assert token["cognito:groups"] == ["human_agent"]


@pytest.mark.parametrize(
    ("role", "client"),
    [
        ("customer", "staff"),
        ("staff", "customer"),
        ("no_group", "customer"),
        ("no_group", "staff"),
    ],
)
def test_a_user_gets_no_token_from_the_other_sides_client(
    users: dict[str, User], sign_in: SignIn, role: str, client: str
) -> None:
    with pytest.raises(ClientError):
        sign_in(users[role], client)


def test_a_customer_cant_rewrite_their_customer_id(
    outputs: dict[str, Any],
    users: dict[str, User],
    sign_in: SignIn,
    cognito: CognitoIdentityProviderClient,
) -> None:
    public = boto3.client(
        "cognito-idp",
        region_name="us-east-1",
        config=Config(signature_version=UNSIGNED),
    )
    customer = users["customer"]
    access = sign_in(customer, "customer")["access"]

    with pytest.raises(ClientError):
        public.update_user_attributes(
            AccessToken=access,
            UserAttributes=[
                {"Name": "custom:customer_id", "Value": "CLI-ITEST0000002"}
            ],
        )
    public.update_user_attributes(
        AccessToken=access, UserAttributes=[{"Name": "locale", "Value": "pt-BR"}]
    )

    stored = cognito.admin_get_user(
        UserPoolId=outputs["user_pool_id"], Username=customer.username
    )["UserAttributes"]
    assert {"Name": "custom:customer_id", "Value": customer.customer_id} in stored
    assert claims(sign_in(customer, "customer")["access"])["customer_id"] == (
        customer.customer_id
    )


# The Gateway and Cedar (ADR-0004, spike S3)


def test_the_gateway_turns_away_a_missing_id_or_staff_token(
    outputs: dict[str, Any], users: dict[str, User], sign_in: SignIn
) -> None:
    assert mcp(outputs, None, "tools/list", {})[0] == 401
    assert mcp(outputs, sign_in(users["customer"], "customer")["id"], "tools/list", {})[
        0
    ] in (401, 403)
    assert mcp(outputs, sign_in(users["staff"], "staff")["access"], "tools/list", {})[
        0
    ] in (401, 403)


def test_a_customer_lists_the_read_tools(
    outputs: dict[str, Any], users: dict[str, User], sign_in: SignIn
) -> None:
    access = sign_in(users["customer"], "customer")["access"]

    status, body = mcp(outputs, access, "tools/list", {})

    assert status == 200
    names = {tool["name"] for tool in body["result"]["tools"]}
    target = outputs["gateway_target"]
    assert names == {f"{target}___list_cards", f"{target}___get_card"}


def test_a_customers_own_call_reaches_the_tool_which_validates_it(
    outputs: dict[str, Any], users: dict[str, User], sign_in: SignIn
) -> None:
    customer = users["customer"]
    assert customer.customer_id is not None
    access = sign_in(customer, "customer")["access"]

    body = call(
        outputs, access, "get_card", get_card(customer.customer_id, "4123456789014821")
    )

    assert tool_output(body) == {
        "outcome": "invalid_input",
        "errors": [{"path": "/card_id", "rule": "pattern"}],
    }


@pytest.mark.parametrize("customer_id", ["CLI-ITEST0000002", "cli-itest0000001"])
def test_cedar_denies_another_customers_id(
    outputs: dict[str, Any], users: dict[str, User], sign_in: SignIn, customer_id: str
) -> None:
    access = sign_in(users["customer"], "customer")["access"]

    body = call(outputs, access, "get_card", get_card(customer_id))

    assert body["error"]["code"] == DENIED


def test_cedar_denies_a_customer_without_the_claim(
    outputs: dict[str, Any], users: dict[str, User], sign_in: SignIn
) -> None:
    access = sign_in(users["no_claim"], "customer")["access"]
    assert "customer_id" not in claims(access)

    body = call(outputs, access, "get_card", get_card("CLI-ITEST0000001"))

    assert body["error"]["code"] == DENIED


# The Runtime (ADR-0004, spike S4)


def test_the_runtime_answers_the_browsers_preflight(outputs: dict[str, Any]) -> None:
    response = httpx.options(
        outputs["invoke_url"],
        headers={
            "Origin": "https://example.cloudfront.net",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": (
                "authorization,content-type,x-amzn-bedrock-agentcore-runtime-session-id"
            ),
        },
        timeout=30,
    )

    assert response.status_code == 200
    assert "access-control-allow-origin" in response.headers


def test_the_runtime_turns_away_a_missing_id_or_staff_token(
    outputs: dict[str, Any], users: dict[str, User], sign_in: SignIn
) -> None:
    assert invoke(outputs, None).status_code == 401
    assert (
        invoke(outputs, sign_in(users["customer"], "customer")["id"]).status_code == 401
    )
    assert invoke(outputs, sign_in(users["staff"], "staff")["access"]).status_code in (
        401,
        403,
    )


def test_a_customer_gets_the_placeholder_reply_after_the_key_is_fetched(
    outputs: dict[str, Any], users: dict[str, User], sign_in: SignIn
) -> None:
    response = invoke(outputs, sign_in(users["customer"], "customer")["access"])

    assert response.status_code == 200
    received = events(response)
    assert [e["type"] for e in received] == [
        "RUN_STARTED",
        "TEXT_MESSAGE_START",
        "TEXT_MESSAGE_CONTENT",
        "TEXT_MESSAGE_END",
        "RUN_FINISHED",
    ], "a RUN_ERROR here usually means the model key isn't stored yet"
    assert received[2]["delta"] == REPLY


# Retention (OPS-10, spike S4)


def test_every_log_group_of_the_stack_keeps_a_retention(
    outputs: dict[str, Any],
) -> None:
    logs = boto3.client("logs", region_name="us-east-1")
    prefixes = [
        f"/aws/lambda/{outputs['prefix']}-",
        outputs["runtime_log_group"].removesuffix("-DEFAULT"),
    ]
    groups = [
        group
        for prefix in prefixes
        for page in logs.get_paginator("describe_log_groups").paginate(
            logGroupNamePrefix=prefix
        )
        for group in page["logGroups"]
    ]

    assert {g["logGroupName"] for g in groups} >= {outputs["runtime_log_group"]}
    assert [g["logGroupName"] for g in groups if "retentionInDays" not in g] == []
