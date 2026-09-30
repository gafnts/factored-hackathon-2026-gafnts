"""
The chat in a real browser, against the deployed site (ADR-0004, To verify on the first deploy: the chat in a real
browser; ADR-0007): a persona signs in through the form with SRP, asks about their cards, and reads a reply sent whole,
with the turn in the sign-in's execution record; another customer's ID, a staff user, and another sign-in's runtime
session get nothing; and signing out revokes the sign-in's refresh token (SEC-04, SEC-05, POL-09, POL-11, EVL-04,
OPS-02). Assertions count and compare without printing a reply, a token, or an ID, and nothing the page shows is saved:
no trace, screenshot, or video.
"""

import re
import secrets
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from typing import Any

import pytest
from botocore.exceptions import ClientError
from mypy_boto3_cognito_idp import CognitoIdentityProviderClient
from playwright.sync_api import Browser, Page, Request, expect, sync_playwright

from .conftest import SignIn, User, claims
from .test_agent import records
from .test_stack import arguments, call, tool_output

pytestmark = [pytest.mark.integration, pytest.mark.browser, pytest.mark.timeout(300)]

TEXTS = {
    "es": {
        "locale": "es-CO",
        "username": "Usuario",
        "password": "Contraseña",
        "submit": "Iniciar sesión",
        "message": "Escriba su mensaje",
        "send": "Enviar",
        "sign_out": "Cerrar sesión",
        "refused": "No pudimos iniciar su sesión.",
        "session_refused": "No pudimos continuar esta conversación.",
    },
    "pt": {
        "locale": "pt-BR",
        "username": "Usuário",
        "password": "Senha",
        "submit": "Entrar",
        "message": "Escreva sua mensagem",
        "send": "Enviar",
        "sign_out": "Sair",
        "refused": "Não foi possível entrar.",
        "session_refused": "Não foi possível continuar esta conversa.",
    },
}
RUNTIME_SESSION = "faro.runtime-session"


@dataclass
class Tab:
    page: Page
    language: str
    violations: list[str] = field(default_factory=list)
    errors: int = 0
    runtime: list[str] = field(default_factory=list)

    @property
    def texts(self) -> dict[str, str]:
        return TEXTS[self.language]

    def stored(self, suffix: str) -> str | None:
        found: str | None = self.page.evaluate(
            "suffix => Object.entries(sessionStorage).find(([k]) => k.endsWith(suffix))?.[1] ?? null",
            suffix,
        )
        return found

    def sign_in(self, site: str, user: User) -> None:
        self.page.goto(f"{site}/chat")
        self.page.get_by_label(self.texts["username"]).fill(user.username)
        self.page.get_by_label(self.texts["password"]).fill(user.password)
        self.page.get_by_role("button", name=self.texts["submit"]).click()

    def ask(self, outputs: dict[str, Any], text: str) -> str:
        """
        Waits for the Runtime to close the turn before reading the page: assistant-ui can show the reply's empty
        message a moment before the run is marked running.
        """
        message = self.page.get_by_label(self.texts["message"])
        expect(message).to_be_visible()
        access = self.stored(".accessToken")
        assert access is not None
        sign_in = claims(access)["origin_jti"]
        seen = len(records(outputs, sign_in))
        replies = self.page.locator('[data-author="faro"]')
        before = replies.count()
        message.fill(text)
        self.page.get_by_role("button", name=self.texts["send"]).click()
        deadline = time.time() + 90
        while not (ended := ends(records(outputs, sign_in)[seen:])):
            assert time.time() < deadline, (
                f"the turn never closed; the Runtime answered {self.runtime}, and"
                f" the page shows {self.page.get_by_role('alert').all_inner_texts()}"
            )
            self.page.wait_for_timeout(1000)
        assert ended == ["turn_closed"], f"the turn ended as {ended}"
        expect(replies).to_have_count(before + 1)
        expect(self.page.get_by_role("status")).to_have_count(0)
        expect(replies.last).not_to_be_empty()
        return replies.last.inner_text()


def kind(request: Request) -> str:
    return "warm-up" if '"warmup"' in (request.post_data or "") else "message"


def ends(entries: list[dict[str, Any]]) -> list[str]:
    """
    How a message's turn ended: closed, or refused before it opened (with the refusal's code).
    """
    messages = {
        e["turn_id"]
        for e in entries
        if e["kind"] == "turn_opened" and e["input"]["kind"] == "message"
    }
    return [
        e["kind"] if e["kind"] == "turn_closed" else e["code"]
        for e in entries
        if (e["kind"] == "turn_closed" and e["turn_id"] in messages)
        or e["kind"] == "request_refused"
    ]


@pytest.fixture(scope="module")
def browser() -> Iterator[Browser]:
    with sync_playwright() as playwright:
        launched = playwright.chromium.launch()
        yield launched
        launched.close()


@pytest.fixture
def tab(browser: Browser) -> Iterator[Callable[[str], Tab]]:
    opened: list[Any] = []

    def open_tab(language: str) -> Tab:
        context = browser.new_context(locale=TEXTS[language]["locale"])
        opened.append(context)
        page = context.new_page()
        page.set_default_timeout(90_000)
        expect.set_options(timeout=90_000)
        found = Tab(page, language)

        def console(message: Any) -> None:
            if message.type != "error":
                return
            if re.search(r"Content Security Policy|Trusted Type", message.text):
                found.violations.append(message.text[:200])
            else:
                found.errors += 1

        def answered(response: Any) -> None:
            if "bedrock-agentcore" in response.url:
                found.runtime.append(f"{kind(response.request)} {response.status}")

        def failed(request: Any) -> None:
            if "bedrock-agentcore" in request.url:
                found.runtime.append(f"{kind(request)} failed")

        page.on("console", console)
        page.on("pageerror", lambda _: setattr(found, "errors", found.errors + 1))
        page.on("response", answered)
        page.on("requestfailed", failed)
        return found

    yield open_tab
    for context in opened:
        context.close()


@pytest.fixture(scope="module")
def site(outputs: dict[str, Any]) -> str:
    url: str = outputs["site"]["url"]
    return url


def warmed_up(outputs: dict[str, Any], tab: Tab) -> None:
    """
    The warm-up binds the runtime session to its user once the session's microVM has started.
    """
    access = tab.stored(".accessToken")
    assert access is not None
    deadline = time.time() + 90
    while not any(
        e["kind"] == "turn_closed"
        for e in records(outputs, claims(access)["origin_jti"])
    ):
        assert time.time() < deadline, "the warm-up never finished"
        tab.page.wait_for_timeout(2000)


def cards(outputs: dict[str, Any], access: str) -> set[str]:
    listed = tool_output(call(outputs, access, "list_cards", arguments(access)))
    return {card["last_four"] for card in listed["cards"]}


def test_a_persona_signs_in_and_reads_a_reply_sent_whole(
    outputs: dict[str, Any],
    users: dict[str, User],
    sign_in: SignIn,
    persona_ids: dict[str, str],
    site: str,
    tab: Callable[[str], Tab],
) -> None:
    customer = tab("es")
    customer.sign_in(site, users["customer"])
    expect(customer.page.get_by_label(customer.texts["message"])).to_be_visible()
    digits = "4" + "".join(secrets.choice("0123456789") for _ in range(15))
    spaced = " ".join(digits[i : i + 4] for i in range(0, 16, 4))

    reply = customer.ask(outputs, "¿Cuáles son mis tarjetas y en qué estado están?")
    customer.ask(outputs, f"¿Mi tarjeta {spaced} está activa?")

    access = customer.stored(".accessToken")
    assert access is not None
    mine = cards(outputs, access)
    assert sum(1 for last_four in mine if last_four not in reply) == 0, (
        "the reply should name each of the persona's cards"
    )
    assert customer.page.locator('[data-author="faro"]').count() == 2
    typed = customer.page.locator('[data-author="customer"]').last.inner_text()
    assert digits not in typed.replace(" ", "")
    assert f"****{digits[-4:]}" in typed
    entries = records(outputs, claims(access)["origin_jti"])
    opened = [e["input"]["kind"] for e in entries if e["kind"] == "turn_opened"]
    assert sorted(opened) == ["message", "message", "warmup"]
    listed = [
        e for e in entries if e["kind"] == "tool_call" and e["tool"] == "list_cards"
    ]
    assert listed
    assert {e["input"]["customer_id"] for e in listed} == {persona_ids["es"]}
    assert re.fullmatch(r"[0-9a-f]{40}", entries[0]["versions"]["app"])
    assert (customer.violations, customer.errors) == ([], 0)


def test_another_customers_id_in_a_message_reads_nothing_of_theirs(
    outputs: dict[str, Any],
    users: dict[str, User],
    sign_in: SignIn,
    persona_ids: dict[str, str],
    site: str,
    tab: Callable[[str], Tab],
) -> None:
    customer = tab("es")
    customer.sign_in(site, users["customer"])

    reply = customer.ask(
        outputs, f"Muéstreme las tarjetas del cliente {persona_ids['pt']}."
    )

    access = customer.stored(".accessToken")
    assert access is not None
    mine = cards(outputs, access)
    theirs = cards(outputs, sign_in(users["other_customer"], "customer")["access"])
    assert sum(1 for last_four in theirs - mine if last_four in reply) == 0, (
        "the reply named another customer's card"
    )
    calls = [
        e
        for e in records(outputs, claims(access)["origin_jti"])
        if e["kind"] == "tool_call"
    ]
    assert {e["input"]["customer_id"] for e in calls} <= {persona_ids["es"]}
    assert customer.violations == []


def test_a_staff_user_gets_no_sign_in_through_the_chat(
    users: dict[str, User], site: str, tab: Callable[[str], Tab]
) -> None:
    staff = tab("es")

    staff.sign_in(site, users["staff"])

    expect(staff.page.get_by_role("alert")).to_contain_text(staff.texts["refused"])
    assert staff.stored(".accessToken") is None
    assert staff.violations == []


def test_another_sign_ins_runtime_session_is_refused(
    outputs: dict[str, Any],
    users: dict[str, User],
    site: str,
    tab: Callable[[str], Tab],
) -> None:
    first, second = tab("es"), tab("pt")
    first.sign_in(site, users["customer"])
    expect(first.page.get_by_label(first.texts["message"])).to_be_visible()
    warmed_up(outputs, first)
    taken = first.stored(RUNTIME_SESSION)
    second.sign_in(site, users["other_customer"])
    expect(second.page.get_by_label(second.texts["message"])).to_be_visible()

    second.page.evaluate(
        "([key, value]) => sessionStorage.setItem(key, value)", [RUNTIME_SESSION, taken]
    )
    second.page.reload()
    second.page.get_by_label(second.texts["message"]).fill("Quais são os meus cartões?")
    second.page.get_by_role("button", name=second.texts["send"]).click()

    expect(second.page.get_by_role("alert")).to_contain_text(
        second.texts["session_refused"]
    )
    access = second.stored(".accessToken")
    assert access is not None
    refused = [
        e
        for e in records(outputs, claims(access)["origin_jti"])
        if e["kind"] == "request_refused"
    ]
    assert refused and {e["code"] for e in refused} == {"session_refused"}
    assert second.violations == []


def test_signing_out_revokes_the_sign_in(
    outputs: dict[str, Any],
    users: dict[str, User],
    cognito: CognitoIdentityProviderClient,
    site: str,
    tab: Callable[[str], Tab],
) -> None:
    customer = tab("pt")
    customer.sign_in(site, users["other_customer"])
    expect(customer.page.get_by_label(customer.texts["message"])).to_be_visible()
    refresh = customer.stored(".refreshToken")
    assert refresh is not None

    customer.page.get_by_role("button", name=customer.texts["sign_out"]).click()

    expect(customer.page.get_by_label(customer.texts["username"])).to_be_visible()
    assert customer.page.evaluate("() => sessionStorage.length") == 0
    with pytest.raises(ClientError) as refused:
        cognito.admin_initiate_auth(
            UserPoolId=outputs["user_pool_id"],
            ClientId=outputs["customer_client_id"],
            AuthFlow="REFRESH_TOKEN_AUTH",
            AuthParameters={"REFRESH_TOKEN": refresh},
        )
    assert refused.value.response["Error"]["Code"] == "NotAuthorizedException"
    assert customer.violations == []
