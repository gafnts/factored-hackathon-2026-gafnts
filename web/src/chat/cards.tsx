import type { ExtraProps } from "react-markdown";

import type { Language } from "../contracts/chat";
import { WORDS } from "../contracts/words";

type Node = NonNullable<ExtraProps["node"]>;

export interface Card {
  name: string;
  status: string;
  expiration: string;
}

const LANGUAGES: readonly Language[] = ["es", "pt"];

function escaped(text: string): string {
  return text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function capitalized(text: string): string {
  return text.charAt(0).toUpperCase() + text.slice(1);
}

function anyOf(words: Record<string, string>, shown = (word: string) => word) {
  return Object.values(words)
    .map((word) => escaped(shown(word)))
    .join("|");
}

// A card in a status answer, as the agent's code writes it (formats.card_line), in the reply words. The reply check
// keeps every digit the model writes inside a placeholder, so no line of the model's own can pass for one.
function cardLine(language: Language): RegExp {
  const types = anyOf(WORDS.product_type[language], capitalized);
  const ending = escaped(WORDS.card_ending[language]);
  const statuses = anyOf(WORDS.product_status[language]);
  const label = escaped(WORDS.expiration_label[language]);
  const unrecorded = escaped(WORDS.expiration_unrecorded[language]);
  return new RegExp(
    `^((?:${types}) ${ending} [0-9]{4}): (${statuses}); (${label}): ([0-9]{2}/[0-9]{4}|${unrecorded})$`,
  );
}

const LINES = LANGUAGES.map(cardLine);

// A list item's text, when it holds text alone.
function itemText(item: Node["children"][number]): string | null {
  if (item.type !== "element" || item.tagName !== "li") return null;
  const [only, ...rest] = item.children;
  return only?.type === "text" && rest.length === 0 ? only.value : null;
}

// The cards a list states, when every item is a card line of one language; otherwise null, and the list stays one.
export function cardsIn(list: Node | undefined): Card[] | null {
  const items = (list?.children ?? []).filter(
    (child) => child.type !== "text" || child.value.trim() !== "",
  );
  const texts = items.map(itemText);
  if (texts.length === 0) return null;
  for (const line of LINES) {
    const cards: Card[] = [];
    for (const text of texts) {
      const found = text === null ? null : line.exec(text);
      const [, name, status, label, expiration] = found ?? [];
      if (!name || !status || !label || !expiration) break;
      cards.push({
        name,
        status: capitalized(status),
        expiration: `${capitalized(label)}: ${expiration}`,
      });
    }
    if (cards.length === texts.length) return cards;
  }
  return null;
}

// The confirm control's frame without its glass: a reply sits on the ground (the identity guide's Motifs).
export function Cards({ cards }: { cards: Card[] }) {
  return (
    <ul data-cards className="grid list-none gap-2 pl-0 sm:grid-cols-2">
      {/* Two cards of a type can share the last four digits (POL-15), so the key is the place. */}
      {cards.map((card, index) => (
        <li
          key={index}
          className="my-0 flex flex-col gap-1 border border-white/10 p-4"
        >
          <p className="font-medium text-balance">{card.name}</p>
          <p>{card.status}</p>
          <p className="text-sm text-bone-muted">{card.expiration}</p>
        </li>
      ))}
    </ul>
  );
}
