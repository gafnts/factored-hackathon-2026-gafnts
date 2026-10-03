import type { ExtraProps } from "react-markdown";

import type { Language } from "../contracts/chat";

export type Node = NonNullable<ExtraProps["node"]>;

export const LANGUAGES: readonly Language[] = ["es", "pt"];

// A pattern's groups, an unmatched one undefined.
export type Found = (string | undefined)[];

// A status's color, always beside its word: starboard's green for one that is well, port's red for one that stops
// (the identity guide's Palette).
export type Tone = "good" | "bad" | "neutral";

export const TONE_CLASS: Record<Tone, string> = {
  good: "text-starboard",
  bad: "text-port",
  neutral: "text-bone-muted",
};

// Each status's tone by the word a reply states it in; the two languages share none of these words.
export function tones<K extends string>(
  words: Record<Language, Record<K, string>>,
  of: Record<K, Tone>,
): (word: string) => Tone {
  const byWord = new Map<string, Tone>();
  for (const language of LANGUAGES) {
    for (const [code, word] of Object.entries(words[language]) as [
      K,
      string,
    ][]) {
      byWord.set(word, of[code]);
    }
  }
  return (word) => byWord.get(word.toLowerCase()) ?? "neutral";
}

export function escaped(text: string): string {
  return text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

export function capitalized(text: string): string {
  return text.charAt(0).toUpperCase() + text.slice(1);
}

export function anyOf(
  words: Record<string, string>,
  shown = (word: string) => word,
): string {
  return Object.values(words)
    .map((word) => escaped(shown(word)))
    .join("|");
}

function itemText(item: Node["children"][number]): string | null {
  if (item.type !== "element" || item.tagName !== "li") return null;
  const [only, ...rest] = item.children;
  return only?.type === "text" && rest.length === 0 ? only.value : null;
}

// The text of each item of a list, when every item holds text alone; otherwise null.
export function itemTexts(list: Node | undefined): string[] | null {
  const texts = (list?.children ?? [])
    .filter((child) => child.type !== "text" || child.value.trim() !== "")
    .map(itemText);
  if (texts.length === 0) return null;
  return texts.every((text) => text !== null) ? texts : null;
}

// Each text read through one pattern; null unless the pattern matches every one and read takes it.
export function readAll<T>(
  texts: string[],
  pattern: RegExp,
  read: (found: Found) => T | null,
): T[] | null {
  const items: T[] = [];
  for (const text of texts) {
    const found = pattern.exec(text);
    const item = found && read([...found]);
    if (!item) return null;
    items.push(item);
  }
  return items;
}
