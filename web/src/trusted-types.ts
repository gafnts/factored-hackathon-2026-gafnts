// TypeScript's DOM library doesn't declare Trusted Types yet.
declare global {
  interface Window {
    trustedTypes?: {
      createPolicy(
        name: string,
        rules: { createHTML: (value: string) => string },
      ): unknown;
    };
  }
}

const CHARACTER_REFERENCE = /^&[A-Za-z0-9]{1,32};$/;

// The Markdown parser decodes a named character reference such as &amp; through innerHTML; nothing else may write
// HTML (ADR-0007, the content security policy's Trusted Types).
export function allowCharacterReference(value: string): string {
  if (CHARACTER_REFERENCE.test(value)) return value;
  throw new TypeError("The site's Trusted Types policy allows no other HTML.");
}

export function installPolicy(): void {
  window.trustedTypes?.createPolicy("default", {
    createHTML: allowCharacterReference,
  });
}
