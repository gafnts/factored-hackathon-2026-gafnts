const KEY = "faro.runtime-session";

// The Runtime needs at least 33 characters; 64 hex digits carry 256 random bits.
export function drawRuntimeSession(): string {
  const bytes = crypto.getRandomValues(new Uint8Array(32));
  const id = Array.from(bytes, (byte) =>
    byte.toString(16).padStart(2, "0"),
  ).join("");
  window.sessionStorage.setItem(KEY, id);
  return id;
}

export function runtimeSession(): string {
  return window.sessionStorage.getItem(KEY) ?? drawRuntimeSession();
}

export function dropRuntimeSession(): void {
  window.sessionStorage.removeItem(KEY);
}
