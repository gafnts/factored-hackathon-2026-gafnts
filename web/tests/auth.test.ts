import { fetchAuthSession, signIn, signOut } from "@aws-amplify/auth";
import { cognitoUserPoolsTokenProvider } from "@aws-amplify/auth/cognito";
import { Amplify, sessionStorage } from "@aws-amplify/core";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import {
  accessToken,
  configureAuth,
  currentSignIn,
  SIGN_IN_LASTS_MS,
  SignInEndedError,
  signInWith,
  signOutHere,
} from "../src/auth";
import { drawRuntimeSession } from "../src/session";

vi.mock("@aws-amplify/auth", () => ({
  fetchAuthSession: vi.fn(),
  signIn: vi.fn(),
  signOut: vi.fn(),
}));

const AUTH_TIME = 1_790_000_000;
const SUB = "3f1e2d3c-4b5a-4968-8776-655443322110";

function session(
  payload: Record<string, unknown> = { sub: SUB, auth_time: AUTH_TIME },
) {
  vi.mocked(fetchAuthSession).mockResolvedValue({
    tokens: {
      accessToken: { payload, toString: () => "the-access-token" },
    },
  } as unknown as Awaited<ReturnType<typeof fetchAuthSession>>);
}

beforeEach(() => {
  vi.useFakeTimers({ toFake: ["Date"] });
  vi.setSystemTime(AUTH_TIME * 1000 + 10 * 60 * 1000);
});

afterEach(() => {
  vi.useRealTimers();
  vi.resetAllMocks();
});

test.each([
  ["customers", "customers-client"],
  ["staff", "staff-client"],
] as const)(
  "keeps the tokens in the tab's sessionStorage, for the %s app client",
  (side, client) => {
    const storage = vi.spyOn(
      cognitoUserPoolsTokenProvider,
      "setKeyValueStorage",
    );
    const configure = vi.spyOn(Amplify, "configure");

    configureAuth(
      {
        region: "us-east-1",
        user_pool_id: "us-east-1_pool",
        customer_client_id: "customers-client",
        staff_client_id: "staff-client",
        runtime_url: "https://runtime.example",
      },
      side,
    );

    expect(storage).toHaveBeenCalledWith(sessionStorage);
    expect(configure).toHaveBeenCalledWith(
      {
        Auth: {
          Cognito: {
            userPoolId: "us-east-1_pool",
            userPoolClientId: client,
          },
        },
      },
      { Auth: { tokenProvider: cognitoUserPoolsTokenProvider } },
    );
  },
);

test("a sign-in ends an hour after it began, whatever the refreshes (POL-09)", async () => {
  session();

  expect(await currentSignIn()).toEqual({
    sub: SUB,
    endsAt: AUTH_TIME * 1000 + SIGN_IN_LASTS_MS,
  });
  expect(SIGN_IN_LASTS_MS).toBe(60 * 60 * 1000);
});

test.each([
  ["no tokens", () => vi.mocked(fetchAuthSession).mockResolvedValue({})],
  [
    "a token without auth_time",
    () => {
      session({ sub: SUB });
    },
  ],
  [
    "a failure",
    () => vi.mocked(fetchAuthSession).mockRejectedValue(new Error("x")),
  ],
])("there is no sign-in with %s", async (_, arrange) => {
  arrange();

  expect(await currentSignIn()).toBeNull();
});

test("hands out the access token while the sign-in lasts", async () => {
  session();

  expect(await accessToken()).toBe("the-access-token");
});

test("refuses a token once the hour is over, even one that would still validate", async () => {
  session();
  vi.setSystemTime(AUTH_TIME * 1000 + SIGN_IN_LASTS_MS);

  await expect(accessToken()).rejects.toBeInstanceOf(SignInEndedError);
});

test("refuses when Amplify holds no tokens", async () => {
  vi.mocked(fetchAuthSession).mockResolvedValue({});

  await expect(accessToken()).rejects.toBeInstanceOf(SignInEndedError);
});

test("signs in with the username and password, through SRP by default", async () => {
  vi.mocked(signIn).mockResolvedValue({
    isSignedIn: true,
    nextStep: { signInStep: "DONE" },
  });

  expect(await signInWith("persona", "secret")).toBe("signed_in");
  expect(signIn).toHaveBeenCalledWith({
    username: "persona",
    password: "secret",
  });
});

test("a step the form doesn't offer is refused, and leaves nothing behind", async () => {
  vi.mocked(signIn).mockResolvedValue({
    isSignedIn: false,
    nextStep: { signInStep: "CONFIRM_SIGN_IN_WITH_NEW_PASSWORD_REQUIRED" },
  });

  expect(await signInWith("persona", "secret")).toBe("refused");
  expect(signOut).toHaveBeenCalled();
});

test.each([
  ["NotAuthorizedException", "refused"],
  ["UserLambdaValidationException", "refused"],
  ["NetworkError", "unreachable"],
])("a sign-in failing with %s is %s", async (name, outcome) => {
  vi.mocked(signIn).mockRejectedValue(Object.assign(new Error("x"), { name }));

  expect(await signInWith("persona", "secret")).toBe(outcome);
});

test("signs out this sign-in only, and drops its runtime session", async () => {
  drawRuntimeSession();

  await signOutHere();

  expect(signOut).toHaveBeenCalledWith();
  expect(window.sessionStorage.length).toBe(0);
});
