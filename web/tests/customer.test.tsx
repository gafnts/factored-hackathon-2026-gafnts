import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import { currentSignIn, signInWith, signOutHere } from "../src/auth";
import { loadConfig } from "../src/config";
import { Customer } from "../src/customer";
import { drawRuntimeSession } from "../src/session";
import { TEXTS } from "../src/texts";

vi.mock(import("../src/config"), async (original) => ({
  ...(await original()),
  loadConfig: vi.fn(),
}));

vi.mock(import("../src/auth"), async (original) => ({
  ...(await original()),
  configureAuth: vi.fn(),
  currentSignIn: vi.fn(),
  signInWith: vi.fn(),
  signOutHere: vi.fn(() => Promise.resolve()),
}));

const CONFIG = {
  region: "us-east-1",
  user_pool_id: "us-east-1_pool",
  customer_client_id: "customers-client",
  runtime_url: "https://runtime.example",
};
const texts = TEXTS.es;

function signedIn(endsIn = 30 * 60 * 1000) {
  return { sub: "sub", endsAt: Date.now() + endsIn };
}

async function signInThroughTheForm() {
  const user = userEvent.setup();
  await user.type(
    await screen.findByLabelText(texts.signIn.username),
    " persona ",
  );
  await user.type(screen.getByLabelText(texts.signIn.password), "secret");
  await user.click(screen.getByRole("button", { name: texts.signIn.submit }));
}

beforeEach(() => {
  vi.mocked(loadConfig).mockResolvedValue(CONFIG);
  vi.mocked(currentSignIn).mockResolvedValue(null);
});

afterEach(() => {
  vi.clearAllMocks();
});

test("says the app couldn't load when config.json can't be read", async () => {
  vi.mocked(loadConfig).mockRejectedValue(new Error("x"));
  render(<Customer language="es" />);

  expect(await screen.findByText(texts.broken)).toBeInTheDocument();
});

test("signs in through the form and draws a runtime session of its own", async () => {
  vi.mocked(signInWith).mockResolvedValue("signed_in");
  vi.mocked(currentSignIn)
    .mockResolvedValueOnce(null)
    .mockResolvedValue(signedIn());
  render(<Customer language="es" />);

  await signInThroughTheForm();

  expect(
    await screen.findByText(/Su sesión termina a las/),
  ).toBeInTheDocument();
  expect(signInWith).toHaveBeenCalledWith("persona", "secret");
  expect(window.sessionStorage.getItem("faro.runtime-session")).toMatch(
    /^[0-9a-f]{64}$/,
  );
  expect(screen.getByText(texts.notice)).toBeInTheDocument();
});

test.each([
  ["refused", texts.signIn.refused],
  ["unreachable", texts.signIn.unreachable],
] as const)(
  "a sign-in %s shows its fixed sentence",
  async (outcome, sentence) => {
    vi.mocked(signInWith).mockResolvedValue(outcome);
    render(<Customer language="es" />);

    await signInThroughTheForm();

    expect(await screen.findByRole("alert")).toHaveTextContent(sentence);
    expect(
      screen.getByRole("button", { name: texts.signIn.submit }),
    ).toBeEnabled();
  },
);

test("a sign-in that leaves no readable token is refused", async () => {
  vi.mocked(signInWith).mockResolvedValue("signed_in");
  render(<Customer language="es" />);

  await signInThroughTheForm();

  expect(await screen.findByRole("alert")).toHaveTextContent(
    texts.signIn.refused,
  );
});

test("a reload keeps the sign-in and its runtime session", async () => {
  const session = drawRuntimeSession();
  vi.mocked(currentSignIn).mockResolvedValue(signedIn());
  render(<Customer language="es" />);

  expect(
    await screen.findByText(/Su sesión termina a las/),
  ).toBeInTheDocument();
  expect(window.sessionStorage.getItem("faro.runtime-session")).toBe(session);
});

test("a reload after the hour ends the sign-in", async () => {
  vi.mocked(currentSignIn).mockResolvedValue(signedIn(-1));
  render(<Customer language="es" />);

  expect(await screen.findByRole("alert")).toHaveTextContent(
    texts.signIn.ended,
  );
  expect(signOutHere).toHaveBeenCalled();
});

test("the hour's end signs the tab out and says so (POL-09)", async () => {
  vi.mocked(currentSignIn).mockResolvedValue(signedIn(100));
  render(<Customer language="es" />);
  await screen.findByText(/Su sesión termina a las/);

  expect(await screen.findByRole("alert")).toHaveTextContent(
    texts.signIn.ended,
  );
  expect(signOutHere).toHaveBeenCalled();
});

test("signing out returns to the form without a message", async () => {
  vi.mocked(currentSignIn).mockResolvedValue(signedIn());
  render(<Customer language="pt" />);

  await userEvent
    .setup()
    .click(
      await screen.findByRole("button", { name: TEXTS.pt.signIn.signOut }),
    );

  expect(
    await screen.findByLabelText(TEXTS.pt.signIn.username),
  ).toBeInTheDocument();
  expect(signOutHere).toHaveBeenCalled();
  await waitFor(() => {
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });
});
