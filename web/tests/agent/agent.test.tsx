import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import { Agent } from "../../src/agent/agent";
import { AGENT } from "../../src/agent/texts";
import {
  configureAuth,
  currentSignIn,
  signInWith,
  signOutHere,
} from "../../src/auth";
import { loadConfig } from "../../src/config";
import { TEXTS } from "../../src/texts";

vi.mock(import("../../src/config"), async (original) => ({
  ...(await original()),
  loadConfig: vi.fn(),
}));

vi.mock(import("../../src/auth"), async (original) => ({
  ...(await original()),
  configureAuth: vi.fn(),
  currentSignIn: vi.fn(),
  signInWith: vi.fn(),
  signOutHere: vi.fn(() => Promise.resolve()),
}));

vi.mock(import("../../src/agent/console"), () => ({
  Console: ({ onEnded }: { onEnded: () => void }) => (
    <div>
      <p>the queues</p>
      <button type="button" onClick={onEnded}>
        the API turned the token away
      </button>
    </div>
  ),
}));

const CONFIG = {
  region: "us-east-1",
  user_pool_id: "us-east-1_pool",
  customer_client_id: "customers-client",
  staff_client_id: "staff-client",
  runtime_url: "https://runtime.example",
};
// The console is in Spanish whatever the browser's language (ADR-0007, Routes).
const texts = TEXTS.es;

function signedIn(endsIn = 30 * 60 * 1000) {
  return { sub: "sub", endsAt: Date.now() + endsIn };
}

async function signInThroughTheForm() {
  const user = userEvent.setup();
  await user.type(
    await screen.findByLabelText(texts.signIn.username),
    " agente ",
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

test("signs in through the staff app client, never the customers'", async () => {
  render(<Agent />);

  expect(
    await screen.findByLabelText(texts.signIn.username),
  ).toBeInTheDocument();
  expect(configureAuth).toHaveBeenCalledWith(CONFIG, "staff");
  expect(screen.getByText(AGENT.title)).toBeInTheDocument();
  expect(screen.getByText(texts.notice)).toBeInTheDocument();
});

test("a human agent signs in and reaches the queues", async () => {
  vi.mocked(signInWith).mockResolvedValue("signed_in");
  vi.mocked(currentSignIn)
    .mockResolvedValueOnce(null)
    .mockResolvedValue(signedIn());
  render(<Agent />);

  await signInThroughTheForm();

  expect(await screen.findByText("the queues")).toBeInTheDocument();
  expect(signInWith).toHaveBeenCalledWith("agente", "secret");
  expect(screen.getByText(/Su sesión terminará a las/)).toBeInTheDocument();
});

test("a customer's credentials, which get no token here, are refused without saying why", async () => {
  vi.mocked(signInWith).mockResolvedValue("refused");
  render(<Agent />);

  await signInThroughTheForm();

  expect(await screen.findByRole("alert")).toHaveTextContent(
    texts.signIn.refused,
  );
  expect(screen.queryByText("the queues")).not.toBeInTheDocument();
});

test("says the app couldn't load when config.json can't be read", async () => {
  vi.mocked(loadConfig).mockRejectedValue(new Error("x"));
  render(<Agent />);

  expect(await screen.findByText(texts.broken)).toBeInTheDocument();
});

test("a reload after the hour ends the sign-in", async () => {
  vi.mocked(currentSignIn).mockResolvedValue(signedIn(-1));
  render(<Agent />);

  expect(await screen.findByRole("alert")).toHaveTextContent(
    texts.signIn.ended,
  );
  expect(signOutHere).toHaveBeenCalled();
});

test("a token the API turns away ends the sign-in", async () => {
  const user = userEvent.setup();
  vi.mocked(currentSignIn).mockResolvedValue(signedIn());
  render(<Agent />);

  await user.click(
    await screen.findByRole("button", {
      name: "the API turned the token away",
    }),
  );

  expect(await screen.findByRole("alert")).toHaveTextContent(
    texts.signIn.ended,
  );
});

test("signing out returns to the form, with no sentence about an ended sign-in", async () => {
  const user = userEvent.setup();
  vi.mocked(currentSignIn).mockResolvedValue(signedIn());
  render(<Agent />);

  await user.click(
    await screen.findByRole("button", { name: texts.signIn.signOut }),
  );

  await waitFor(() => {
    expect(signOutHere).toHaveBeenCalled();
  });
  expect(
    await screen.findByLabelText(texts.signIn.username),
  ).toBeInTheDocument();
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
});
