import type { Language } from "./contracts/chat";

export function browserLanguage(
  preferred: readonly string[] = [...navigator.languages, navigator.language],
): Language {
  return preferred[0]?.toLowerCase().startsWith("pt") ? "pt" : "es";
}
