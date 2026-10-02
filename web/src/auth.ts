import { fetchAuthSession, signIn, signOut } from "@aws-amplify/auth";
import { cognitoUserPoolsTokenProvider } from "@aws-amplify/auth/cognito";
import { Amplify, sessionStorage } from "@aws-amplify/core";

import type { Config } from "./config";
import { dropRuntimeSession } from "./session";

// The refresh token lasts 60 minutes, and no refresh extends it (ADR-0004, decision 10).
export const SIGN_IN_LASTS_MS = 60 * 60 * 1000;

export class SignInEndedError extends Error {
  override name = "SignInEndedError";
}

export interface SignedIn {
  sub: string;
  endsAt: number;
}

export type SignInOutcome = "signed_in" | "refused" | "unreachable";

// Customers sign in through their app client and staff through theirs; the pre-token trigger refuses a token from the
// other side's (ADR-0007, Sign-in). Amplify keys a tab's tokens by client, so the two never mix.
export type Side = "customers" | "staff";

export function configureAuth(config: Config, side: Side): void {
  const auth = {
    Cognito: {
      userPoolId: config.user_pool_id,
      userPoolClientId:
        side === "customers"
          ? config.customer_client_id
          : config.staff_client_id,
    },
  };
  cognitoUserPoolsTokenProvider.setAuthConfig(auth);
  cognitoUserPoolsTokenProvider.setKeyValueStorage(sessionStorage);
  Amplify.configure(
    { Auth: auth },
    { Auth: { tokenProvider: cognitoUserPoolsTokenProvider } },
  );
}

function signedInFrom(payload: Record<string, unknown>): SignedIn | null {
  const { sub, auth_time: authTime } = payload;
  if (typeof sub !== "string" || typeof authTime !== "number") return null;
  return { sub, endsAt: authTime * 1000 + SIGN_IN_LASTS_MS };
}

export async function currentSignIn(): Promise<SignedIn | null> {
  try {
    const { tokens } = await fetchAuthSession();
    return tokens ? signedInFrom(tokens.accessToken.payload) : null;
  } catch {
    return null;
  }
}

// Amplify refreshes the access token when it is due; past the hour, the sign-in is over even if a refreshed token
// would still validate for up to 15 minutes.
export async function accessToken(): Promise<string> {
  const { tokens } = await fetchAuthSession();
  const signedIn = tokens ? signedInFrom(tokens.accessToken.payload) : null;
  if (!tokens || !signedIn || Date.now() >= signedIn.endsAt) {
    throw new SignInEndedError();
  }
  return tokens.accessToken.toString();
}

export async function signInWith(
  username: string,
  password: string,
): Promise<SignInOutcome> {
  try {
    // SRP is the default flow.
    const { isSignedIn } = await signIn({ username, password });
    if (isSignedIn) return "signed_in";
    // A step we don't offer, such as a new password, leaves nothing half done.
    await signOut();
    return "refused";
  } catch (error) {
    return error instanceof Error && error.name === "NetworkError"
      ? "unreachable"
      : "refused";
  }
}

// Never global: it would end every sign-in of the user, and judges share personas (ADR-0007). Amplify revokes this
// sign-in's refresh token and clears the tab's tokens.
export async function signOutHere(): Promise<void> {
  try {
    await signOut();
  } finally {
    dropRuntimeSession();
  }
}
